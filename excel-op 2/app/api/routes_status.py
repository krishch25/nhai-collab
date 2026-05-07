"""Endpoints for checking batch / job status."""

from __future__ import annotations

from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.models import ProcessingJob
from app.db.session import get_db

router = APIRouter(prefix="/status", tags=["status"])


@router.get("/", response_model=List[dict])
def list_batches(
    mode: Optional[str] = Query(None, pattern="^(training|inference|synthesis)$"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Annotated[Session, Depends(get_db)] = None,
):
    """List recent batches with optional filtering by mode."""
    q = db.query(ProcessingJob).order_by(ProcessingJob.created_at.desc())
    if mode is not None:
        q = q.filter(ProcessingJob.job_type == mode.upper())
    q = q.offset(offset).limit(limit)
    uploads = q.all()

    return [
        {
            "batch_id": u.batch_id,
            "file_name": u.file_name,
            "mode": u.job_type,
            "row_count": u.total_rows,
            "processed_rows": u.processed_rows,
            "status": u.status,
            "error_message": u.error_log,
            "created_at": u.created_at,
        }
        for u in uploads
    ]


@router.get("/{batch_id}", response_model=dict)
def get_batch_status(batch_id: str, db: Annotated[Session, Depends(get_db)] = None):
    """Return status information for a single batch_id."""
    upload = (
        db.query(ProcessingJob)
        .filter(ProcessingJob.batch_id == batch_id)
        .order_by(ProcessingJob.created_at.desc())
        .first()
    )
    if upload is None:
        raise HTTPException(404, f"Batch {batch_id} not found")

    return {
        "batch_id": upload.batch_id,
        "file_name": upload.file_name,
        "mode": upload.job_type,
        "row_count": upload.total_rows,
        "processed_rows": upload.processed_rows,
        "status": upload.status,
        "error_message": upload.error_log,
        "created_at": upload.created_at,
    }

