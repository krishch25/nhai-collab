"""CrewAI orchestration for training and inference flows."""

from __future__ import annotations

from typing import List, Sequence

import logging

import pandas as pd
from crewai import Agent as CrewAgent
from crewai import Crew, Process
from sqlalchemy.orm import Session

from app.agents import tasks as task_factory
from app.core.llm import get_chat_llm
from app.db.models import RawData, ProcessingJob

logger = logging.getLogger(__name__)


def _make_base_agent(role: str, goal: str, model_name: str | None = None) -> CrewAgent:
    """Create a CrewAgent backed by our shared Chat LLM."""
    llm = get_chat_llm(temperature=0.0, model_name=model_name)
    return CrewAgent(
        role=role,
        goal=goal,
        backstory="Part of a continuous-learning taxonomy classification system.",
        llm=llm,
        verbose=False,
    )


def build_training_crew(
    raw_df: pd.DataFrame,
    labels_df: pd.DataFrame,
    db: Session,
) -> Crew:
    """
    Build a Crew that runs the training pipeline:
    - Agent 0 (Rule Generator) generates and persists rules from labelled data.
    """

    from app.core.config import get_settings
    settings = get_settings()

    rule_agent = _make_base_agent(
        role="Rule Generator",
        goal="Derive high-quality, explicit IF/THEN rules from labelled material data.",
        model_name=settings.rule_generator_model,
    )

    rule_task = task_factory.make_rule_generation_task(
        agent=rule_agent,
        raw_df=raw_df,
        labels_df=labels_df,
        db=db,
        created_by="agent",
    )

    crew = Crew(
        agents=[rule_agent],
        tasks=[rule_task],
        process=Process.sequential,
        verbose=False,
    )
    return crew


def build_inference_crew(
    db: Session,
    raw_rows: Sequence[RawData],
    *,
    parallel: bool = False,
) -> Crew:
    """
    Build a Crew that runs the inference pipeline:
    - Agent 1 (Decision Maker) classifies each raw row using rules + vectors.
    - Agent 2 (Quality Control) is embedded in the DecisionMakerAgent implementation.
    """

    from app.core.config import get_settings
    settings = get_settings()

    decision_agent = _make_base_agent(
        role="Decision Maker",
        goal="Assign the most appropriate L0/L1/L2 taxonomy to raw materials.",
        model_name=settings.decision_maker_model,
    )

    classification_tasks = task_factory.make_classification_tasks_for_batch(
        agent=decision_agent,
        db=db,
        raw_rows=list(raw_rows),
    )

    crew = Crew(
        agents=[decision_agent],
        tasks=classification_tasks,
        process=Process.parallel if parallel else Process.sequential,
        verbose=False,
    )
    return crew


def run_training_pipeline(
    raw_df: pd.DataFrame,
    labels_df: pd.DataFrame,
    db: Session,
) -> str:
    """Convenience entrypoint to run the full training pipeline synchronously."""
    try:
        from app.agents.agents import RuleGeneratorAgent
        agent = RuleGeneratorAgent()
        rules = agent.generate_rules_from_training(raw_df=raw_df, labels_df=labels_df, max_rules=20)
        agent.persist_rules(db, rules, created_by="agent")
        msg = f"Generated and persisted {len(rules)} explicit rules."
        logger.info(msg)
        return msg
    except Exception as exc:
        logger.exception("Training pipeline failed: %s", exc)
        return f"Training failed: {exc}"


def run_inference_pipeline(
    db: Session,
    raw_rows: Sequence[RawData],
    *,
    job: ProcessingJob | None = None,
    parallel: bool = False,
) -> str:
    """Run the full inference pipeline synchronously with optional progress tracking."""
    try:
        from app.agents.agents import DecisionMakerAgent
        agent = DecisionMakerAgent()
        success_count = 0
        logger.info("Starting inference on %d rows", len(raw_rows))
        for i, row in enumerate(raw_rows):
            agent.classify_row(db, row)
            success_count += 1
            if job:
                job.processed_rows = i + 1
                db.commit()
        msg = f"Successfully classified {success_count} rows."
        logger.info(msg)
        return msg
    except Exception as exc:
        logger.exception("Inference pipeline failed: %s", exc)
        return f"Inference failed: {exc}"


