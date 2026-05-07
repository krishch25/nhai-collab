"""CrewAI-compatible task factories for the taxonomy system.

These tasks wrap the domain agents in `agents.py` so they can be orchestrated
inside a Crew. They can also be called directly in application code.
"""

from __future__ import annotations

from typing import Callable, List

import logging

import pandas as pd
from crewai import Task
from sqlalchemy.orm import Session

from app.agents.agents import DecisionMakerAgent, RuleGeneratorAgent
from app.db.models import RawData

logger = logging.getLogger(__name__)


def make_rule_generation_task(
    agent,
    raw_df: pd.DataFrame,
    labels_df: pd.DataFrame,
    db: Session,
    created_by: str = "agent",
    ) -> Task:
    """Create a CrewAI task that generates and persists rules from training data."""

    def _callable(**kwargs) -> str:
        try:
            generator = RuleGeneratorAgent()
            rules = generator.generate_rules_from_training(raw_df, labels_df)
            generator.persist_rules(db, rules, created_by=created_by)
            logger.info("Generated %d rules from training data", len(rules))
            return f"Generated and persisted {len(rules)} rules."
        except Exception as exc:  # noqa: BLE001
            logger.exception("Rule generation task failed: %s", exc)
            return f"Rule generation failed: {exc}"

    return Task(
        description=(
            "Analyse labelled raw-material data and derive explicit IF/THEN "
            "taxonomy rules that can be stored in the database."
        ),
        agent=agent,
        expected_output=(
            "A summary string confirming how many rules were generated and saved, "
            "or an error message if something failed."
        ),
        callable=_callable,
    )


def make_classification_tasks_for_batch(
    agent,
    db: Session,
    raw_rows: List[RawData],
) -> List[Task]:
    """Create CrewAI tasks that classify each RawData row in a batch."""

    tasks: List[Task] = []

    for row in raw_rows:

        def _classify(row_id=row.id, **kwargs) -> str:
            try:
                row_obj = db.get(RawData, row_id)
                if row_obj is None:
                    logger.warning("RawData row %s not found during classification", row_id)
                    return f"Row {row_id} not found."
                decision_maker = DecisionMakerAgent()
                classification = decision_maker.classify_row(db, row_obj)
                msg = (
                    f"Row {row_id} classified as "
                    f"L0={classification.l0}, L1={classification.l1}, L2={classification.l2}, "
                    f"confidence={classification.confidence}."
                )
                logger.info(msg)
                return msg
            except Exception as exc:  # noqa: BLE001
                logger.exception("Classification task for row %s failed: %s", row_id, exc)
                return f"Classification failed for row {row_id}: {exc}"

        task = Task(
            description=f"Classify raw material row id={row.id} into L0/L1/L2.",
            agent=agent,
            expected_output=(
                "A short text summarising the assigned L0/L1/L2 and confidence, "
                "or an error message if classification failed."
            ),
            callable=_classify,
        )
        tasks.append(task)

    return tasks

