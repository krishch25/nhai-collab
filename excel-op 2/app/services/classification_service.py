"""High-level training and inference services for taxonomy classification.

These functions coordinate:
- Excel ingestion (already done elsewhere)
- Persistence of RawData / FileUpload rows
- CrewAI-based agents & crews for rule generation and classification
"""

from __future__ import annotations

import logging
from typing import Dict, List

import pandas as pd
from sqlalchemy.orm import Session
from app.db.session import SessionLocal

from app.agents.crew import run_inference_pipeline, run_training_pipeline
from app.db.models import ClassifiedOutput, ProcessingJob, RawData
from app.services.excel_service import TRAINING_TAXONOMY_COLS, split_training_dataframe

logger = logging.getLogger(__name__)


def _create_processing_job(
    db: Session,
    *,
    batch_id: str,
    file_name: str,
    mode: str,
    row_count: int,
) -> ProcessingJob:
    job = ProcessingJob(
        batch_id=batch_id,
        file_name=file_name,
        job_type=mode.upper(),
        total_rows=row_count,
        status="PENDING",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _persist_raw_rows(
    db: Session,
    *,
    batch_id: str,
    file_name: str,
    df: pd.DataFrame,
) -> List[RawData]:
    """Persist DataFrame rows into RawData and return the created objects."""
    rows: List[RawData] = []

    for idx, row in df.reset_index(drop=True).iterrows():
        payload = row.to_dict()
        # Choose a sensible default for raw_text; fall back to concatenated string
        material_desc = (
            payload.get("material_description")
            or payload.get("m_desc")
            or payload.get("description")
        )
        if material_desc is None:
            raw_text = " ".join(str(v) for v in payload.values() if v is not None)
        else:
            raw_text = str(material_desc)

        raw = RawData(
            batch_id=batch_id,
            file_name=file_name,
            row_index=int(idx),
            raw_text=raw_text,
            raw_payload=payload,
        )
        db.add(raw)
        rows.append(raw)

    db.commit()
    # Refresh to ensure IDs are populated
    for r in rows:
        db.refresh(r)
    logger.info("Persisted %d RawData rows for batch %s", len(rows), batch_id)
    return rows


def run_training(
    batch_id: str,
    file_name: str,
    df_training: pd.DataFrame,
    created_by: str = "agent",
) -> None:
    """Entrypoint for background training. Handles its own session."""
    db = SessionLocal()
    try:
        upload = _create_processing_job(
            db,
            batch_id=batch_id,
            file_name=file_name,
            mode="training",
            row_count=len(df_training),
        )

        raw_df, labels_df = split_training_dataframe(df_training)

        upload.status = "PROCESSING"
        db.commit()
        
        result = run_training_pipeline(raw_df=raw_df, labels_df=labels_df, db=db)
        
        upload.status = "COMPLETED"
        upload.error_log = None
        upload.completed_at = pd.Timestamp.now()
        db.commit()
        logger.info("Training pipeline for batch %s completed", batch_id)
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        try:
            # Re-fetch in this session to update
            job = db.query(ProcessingJob).filter_by(batch_id=batch_id).first()
            if job:
                job.status = "FAILED"
                job.error_log = str(exc)
                job.completed_at = pd.Timestamp.now()
                db.commit()
        except Exception:
            logger.exception("Final attempt to log error for %s failed", batch_id)
        logger.exception("Training pipeline for batch %s failed: %s", batch_id, exc)
    finally:
        db.close()


def run_inference(
    batch_id: str,
    file_name: str,
    df_inference: pd.DataFrame,
    parallel: bool = False,
) -> None:
    """Entrypoint for background inference. Handles its own session."""
    db = SessionLocal()
    try:
        upload = _create_processing_job(
            db,
            batch_id=batch_id,
            file_name=file_name,
            mode="inference",
            row_count=len(df_inference),
        )

        raw_rows = _persist_raw_rows(
            db,
            batch_id=batch_id,
            file_name=file_name,
            df=df_inference,
        )

        upload.status = "PROCESSING"
        db.commit()
        
        result = run_inference_pipeline(db=db, raw_rows=raw_rows, job=upload, parallel=parallel)
        
        upload.status = "COMPLETED"
        upload.error_log = None
        upload.completed_at = pd.Timestamp.now()
        db.commit()
        logger.info("Inference pipeline for batch %s completed", batch_id)
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        try:
            job = db.query(ProcessingJob).filter_by(batch_id=batch_id).first()
            if job:
                job.status = "FAILED"
                job.error_log = str(exc)
                job.completed_at = pd.Timestamp.now()
                db.commit()
        except Exception:
            logger.exception("Final attempt to log error for %s failed", batch_id)
        logger.exception("Inference pipeline for batch %s failed: %s", batch_id, exc)
    finally:
        db.close()


def get_classified_dataframe_for_batch(db: Session, batch_id: str) -> pd.DataFrame:
    """Build a DataFrame joining RawData and ClassifiedOutput for a batch."""

    q = (
        db.query(RawData, ClassifiedOutput)
        .join(ClassifiedOutput, ClassifiedOutput.raw_data_id == RawData.id)
        .filter(RawData.batch_id == batch_id)
    )

    records: List[Dict[str, object]] = []
    for raw, classified in q.all():
        row = dict(raw.raw_payload or {})
        row.update(
            {
                "batch_id": raw.batch_id,
                "file_name": raw.file_name,
                "row_index": raw.row_index,
                "l0": classified.l0,
                "l1": classified.l1,
                "l2": classified.l2,
                "confidence": classified.confidence,
                "status": classified.status,
                "rule_id": classified.rule_id,
                "vector_match_id": classified.vector_match_id,
                "notes": classified.notes,
            }
        )
        records.append(row)

    if not records:
        return pd.DataFrame()

    return pd.DataFrame.from_records(records)

