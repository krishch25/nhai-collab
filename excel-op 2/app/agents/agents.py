"""Domain agents for rule generation, decision making, and quality control.

These classes wrap LLM calls and database/vector-store access. They can be
used directly or plugged into CrewAI tasks in `crew.py`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd
from sqlalchemy.orm import Session

from app.core.llm import get_chat_llm
from app.db.models import ClassifiedOutput, RawData, RuleAudit, TaxonomyRule
from app.db.vector_store import query_raw_materials, upsert_raw_material, upsert_rule


@dataclass
class ProposedRule:
    name: str
    description: str
    condition_expression: str
    condition_payload: Dict[str, Any]
    l0: str
    l1: str
    l2: str
    confidence: float


@dataclass
class ProposedClassification:
    l0: str
    l1: str
    l2: str
    confidence: float
    provenance: str  # "rule" | "vector"
    rule_id: Optional[int] = None
    vector_match_id: Optional[str] = None
    notes: Optional[str] = None


class RuleGeneratorAgent:
    """Agent 0: Generate explicit IF/THEN rules from labelled examples."""

    def __init__(self, temperature: float = 0.0):
        from app.core.config import get_settings
        settings = get_settings()
        self.llm = get_chat_llm(temperature=temperature, model_name=settings.rule_generator_model)

    def generate_rules_from_training(
        self,
        raw_df: pd.DataFrame,
        labels_df: pd.DataFrame,
        max_rules: int = 20,
    ) -> List[ProposedRule]:
        """
        Ask the LLM to infer a compact set of deterministic rules from training examples.
        Returns a list of ProposedRule objects.
        """
        sample = pd.concat([raw_df, labels_df], axis=1)
        sample = sample.dropna(subset=['l0', 'l1', 'l2'], how='all')
        
        # Helper for LLM calls with retry
        import time
        def invoke_with_retry(prompt_text: str, max_retries: int = 8) -> str:
            for attempt in range(max_retries):
                try:
                    res = self.llm.invoke(prompt_text)
                    return res.content if hasattr(res, "content") else str(res)
                except Exception as e:
                    if "429" in str(e) or "temporarily rate-limited" in str(e):
                        if attempt < max_retries - 1:
                            sleep_time = 10 * (attempt + 1)
                            print(f"Rate limited. Retrying in {sleep_time}s...")
                            time.sleep(sleep_time)
                            continue
                    raise e
            return ""

        proposed: List[ProposedRule] = []
        batch_size = 3  # Extremely small batches to respect limits
        
        for i in range(0, len(sample), batch_size):
            batch_df = sample.iloc[i:i+batch_size]
            sample_json = batch_df.to_json(orient="records")
            print(f"DEBUG Processing batch {i//batch_size + 1}, rows {i} to {i+len(batch_df)}")

            prompt = (
                "You are an expert data classification rule designer.\n"
                "You are given example rows of raw material data with L0/L1/L2 taxonomy labels.\n"
                "Derive a SMALL, EXPLICIT set of deterministic IF/THEN rules that map raw fields\n"
                "to the taxonomy.\n\n"
                "Rules MUST be output as STRICT JSON with this schema (no markdown, no comments):\n"
                "{\n"
                '  \"rules\": [\n'
                "    {\n"
                '      \"name\": \"short_rule_name\",\n'
                '      \"description\": \"human readable description\",\n'
                '      \"condition_expression\": \"SQL-like or human IF expression over fields (e.g. material_description ILIKE \'%copper%\' AND plant_code = \'1000\')\",\n'
                '      \"condition_payload\": {\"type\": \"contains\", \"field\": \"material_description\", \"value\": \"copper\"},\n'
                '      \"l0\": \"...\",\n'
                '      \"l1\": \"...\",\n'
                '      \"l2\": \"...\",\n'
                '      \"confidence\": 0.0\n'
                "    }\n"
                "  ]\n"
                "}\n\n"
                f"Limit yourself to at most {max_rules} rules.\n"
                "Here are example rows as JSON array:\n"
                f"{sample_json}\n"
            )

            content = invoke_with_retry(prompt)

            # Extract text strictly inside json block if framed by markdown ```
            import re
            match = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL | re.IGNORECASE)
            if match:
                clean_content = match.group(1)
            else:
                # Maybe it just starts/ends with braces, try to find the outermost valid { ... }
                start = content.find("{")
                end = content.rfind("}")
                clean_content = content[start:end+1] if start >= 0 and end >= 0 else content

            try:
                data = json.loads(clean_content)
            except json.JSONDecodeError as exc:
                print(f"DEBUG failed to parse json: {clean_content}")
                continue

            rules_data = data.get("rules", [])
            for r in rules_data:
                try:
                    proposed.append(
                        ProposedRule(
                            name=r["name"],
                            description=r.get("description", ""),
                            condition_expression=r.get("condition_expression", ""),
                            condition_payload=r.get("condition_payload") or {},
                            l0=r["l0"],
                            l1=r["l1"],
                            l2=r["l2"],
                            confidence=float(r.get("confidence", 0.0)),
                        )
                    )
                except KeyError:
                    continue

        return proposed

    def persist_rules(self, db: Session, rules: Sequence[ProposedRule], created_by: str = "agent") -> None:
        """Insert ProposedRule objects into the TaxonomyRule table and vector store."""
        for r in rules:
            rule = TaxonomyRule(
                name=r.name,
                description=r.description,
                condition_expression=r.condition_expression,
                condition_payload=r.condition_payload,
                l0=r.l0,
                l1=r.l1,
                l2=r.l2,
                source="agent",
                created_by=created_by,
                confidence=r.confidence,
                is_active=True,
            )
            db.add(rule)
            db.flush()  # to get rule.id

            upsert_rule(
                record_id=str(rule.id),
                document=r.condition_expression or r.description,
                metadata={
                    "l0": r.l0,
                    "l1": r.l1,
                    "l2": r.l2,
                },
            )

            audit = RuleAudit(
                rule_id=rule.id,
                action="created",
                old_values=None,
                new_values={
                    "name": r.name,
                    "l0": r.l0,
                    "l1": r.l1,
                    "l2": r.l2,
                    "condition": r.condition_expression,
                },
                performed_by=created_by,
            )
            db.add(audit)

        db.commit()


class QualityControlAgent:
    """Agent 2: Assign a confidence score and optional comments."""

    def __init__(self, temperature: float = 0.0):
        from app.core.config import get_settings
        settings = get_settings()
        self.llm = get_chat_llm(temperature=temperature, model_name=settings.quality_control_model)

    def evaluate_classification(
        self,
        raw_payload: Dict[str, Any],
        proposed: ProposedClassification,
        neighbors: Optional[Dict[str, Any]] = None,
    ) -> ProposedClassification:
        """
        Use the LLM to refine the confidence score and optionally add notes.
        """
        payload_json = json.dumps(raw_payload, ensure_ascii=False)
        neighbors_json = json.dumps(neighbors or {}, ensure_ascii=False)
        proposed_json = json.dumps(
            {
                "l0": proposed.l0,
                "l1": proposed.l1,
                "l2": proposed.l2,
                "confidence": proposed.confidence,
                "provenance": proposed.provenance,
            }
        )

        prompt = (
            "You are a meticulous quality-control reviewer for taxonomy classification.\n"
            "Given a raw material record, a proposed taxonomy (L0/L1/L2), and optional\n"
            "nearest-neighbour evidence, you must output a JSON object with a refined\n"
            "confidence score between 0 and 1 and an optional short comment.\n\n"
            "Strict output JSON schema:\n"
            "{\n"
            '  \"confidence\": 0.0,\n'
            '  \"comment\": \"short explanation\"\n'
            "}\n\n"
            f"Raw payload JSON:\n{payload_json}\n\n"
            f"Proposed classification JSON:\n{proposed_json}\n\n"
            f"Nearest neighbours JSON (may be empty):\n{neighbors_json}\n"
        )

        import time
        max_retries = 8
        content = ""
        for attempt in range(max_retries):
            try:
                response = self.llm.invoke(prompt)
                content = response.content if hasattr(response, "content") else str(response)
                break
            except Exception as e:
                if "429" in str(e) or "temporarily rate-limited" in str(e):
                    if attempt < max_retries - 1:
                        sleep_time = 10 * (attempt + 1)
                        print(f"Rate limited QC. Retrying in {sleep_time}s...")
                        time.sleep(sleep_time)
                        continue
                raise e
        
        # Extract text strictly inside json block if framed by markdown ```
        import re
        match = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL | re.IGNORECASE)
        if match:
            clean_content = match.group(1)
        else:
            # Maybe it just starts/ends with braces, try to find the outermost valid { ... }
            start = content.find("{")
            end = content.rfind("}")
            clean_content = content[start:end+1] if start >= 0 and end >= 0 else content

        try:
            data = json.loads(clean_content)
        except json.JSONDecodeError:
            data = {"confidence": proposed.confidence, "comment": proposed.notes}

        confidence = float(data.get("confidence", proposed.confidence))
        comment = data.get("comment") or proposed.notes

        proposed.confidence = confidence
        proposed.notes = comment
        return proposed


class DecisionMakerAgent:
    """Agent 1: Decide taxonomy for a new raw material using rules and vectors."""

    def __init__(self, temperature: float = 0.0):
        from app.core.config import get_settings
        settings = get_settings()
        self.llm = get_chat_llm(temperature=temperature, model_name=settings.decision_maker_model)
        self.qc = QualityControlAgent(temperature=temperature)

    def classify_row(
        self,
        db: Session,
        raw: RawData,
        *,
        neighbors_k: int = 5,
    ) -> ClassifiedOutput:
        """
        Classify a single RawData row.

        - First try to match existing active rules (very simple placeholder matching for now).
        - If no strong rule match, query ChromaDB for semantic neighbours and ask the LLM.
        - Run quality-control pass to refine confidence.
        - Persist ClassifiedOutput.
        """
        payload = raw.raw_payload or {}
        text = raw.raw_text or payload.get("material_description") or ""

        # 1) Try to match active rules heuristically (placeholder: all rules with same l0/l1/l2 patterns could be used)
        rule_match = (
            db.query(TaxonomyRule)
            .filter(TaxonomyRule.is_active.is_(True))
            .order_by(TaxonomyRule.confidence.desc().nullslast())
            .first()
        )

        if rule_match is not None:
            proposed = ProposedClassification(
                l0=rule_match.l0 or "",
                l1=rule_match.l1 or "",
                l2=rule_match.l2 or "",
                confidence=rule_match.confidence or 0.8,
                provenance="rule",
                rule_id=rule_match.id,
            )
            refined = self.qc.evaluate_classification(payload, proposed, neighbors=None)
            classified = ClassifiedOutput(
                raw_data_id=raw.id,
                rule_id=refined.rule_id,
                l0=refined.l0,
                l1=refined.l1,
                l2=refined.l2,
                confidence=refined.confidence,
                vector_match_id=refined.vector_match_id,
                status="confirmed" if refined.confidence >= 0.8 else "review",
                notes=refined.notes,
            )
            db.add(classified)
            db.commit()
            db.refresh(classified)
            return classified

        # 2) No rule match: query Chroma for neighbours and ask LLM to infer taxonomy
        upsert_raw_material(
            record_id=str(raw.id),
            document=text,
            metadata=payload,
        )
        neighbors = query_raw_materials(query_text=text, n_results=neighbors_k)

        prompt = (
            "You are a taxonomy decision-maker.\n"
            "Given a raw material record and similar historical records, infer the most\n"
            "likely L0/L1/L2 taxonomy.\n\n"
            "STRICT JSON output only (no markdown):\n"
            "{\n"
            '  \"l0\": \"...\",\n'
            '  \"l1\": \"...\",\n'
            '  \"l2\": \"...\",\n'
            '  \"confidence\": 0.0,\n'
            '  \"vector_match_id\": \"id-of-best-neighbour-or-null\"\n'
            "}\n\n"
            f"Raw payload JSON:\n{json.dumps(payload, ensure_ascii=False)}\n\n"
            f"Nearest neighbours JSON:\n{json.dumps(neighbors, ensure_ascii=False)}\n"
        )

        import time
        max_retries = 8
        content = ""
        for attempt in range(max_retries):
            try:
                response = self.llm.invoke(prompt)
                content = response.content if hasattr(response, "content") else str(response)
                break
            except Exception as e:
                if "429" in str(e) or "temporarily rate-limited" in str(e):
                    if attempt < max_retries - 1:
                        sleep_time = 10 * (attempt + 1)
                        print(f"Rate limited Decision. Retrying in {sleep_time}s...")
                        time.sleep(sleep_time)
                        continue
                raise e

        # Extract text strictly inside json block if framed by markdown ```
        import re
        match = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL | re.IGNORECASE)
        if match:
            clean_content = match.group(1)
        else:
            # Maybe it just starts/ends with braces, try to find the outermost valid { ... }
            start = content.find("{")
            end = content.rfind("}")
            clean_content = content[start:end+1] if start >= 0 and end >= 0 else content

        try:
            data = json.loads(clean_content)
        except json.JSONDecodeError:
            data = {"confidence": 0.5, "vector_match_id": None}

        proposed = ProposedClassification(
            l0=data.get("l0", "") or "",
            l1=data.get("l1", "") or "",
            l2=data.get("l2", "") or "",
            confidence=float(data.get("confidence", 0.6)),
            provenance="vector",
            rule_id=None,
            vector_match_id=(data.get("vector_match_id") or None),
        )

        refined = self.qc.evaluate_classification(payload, proposed, neighbors=neighbors)

        classified = ClassifiedOutput(
            raw_data_id=raw.id,
            rule_id=refined.rule_id,
            l0=refined.l0,
            l1=refined.l1,
            l2=refined.l2,
            confidence=refined.confidence,
            vector_match_id=refined.vector_match_id,
            status="confirmed" if refined.confidence >= 0.8 else "review",
            notes=refined.notes,
        )
        db.add(classified)
        db.commit()
        db.refresh(classified)
        return classified

