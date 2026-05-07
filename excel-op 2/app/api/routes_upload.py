"""Upload endpoints for training and inference Excel files."""

from __future__ import annotations

import io
import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.classification_service import run_inference, run_training
from app.services.excel_service import read_inference_excel, read_training_excel

router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("/training")
async def upload_training(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Annotated[Session, Depends(get_db)] = None,
):
    """Upload an Excel file and trigger asynchronous training."""
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(400, "Expected .xlsx or .xls file")

    contents = await file.read()
    try:
        df = read_training_excel(io.BytesIO(contents))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"Failed to parse training Excel: {exc}") from exc

    batch_id = str(uuid.uuid4())
    # Offload the long-running LLM work to the background
    background_tasks.add_task(
        run_training,
        batch_id=batch_id,
        file_name=file.filename,
        df_training=df,
    )
    
    return {
        "batch_id": batch_id,
        "file_name": file.filename,
        "status": "PENDING",
        "message": "Training job started in background."
    }


@router.post("/inference")
async def upload_inference(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    parallel: bool = False,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """Upload an Excel file and trigger asynchronous inference."""
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(400, "Expected .xlsx or .xls file")

    contents = await file.read()
    try:
        df = read_inference_excel(io.BytesIO(contents))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"Failed to parse inference Excel: {exc}") from exc

    batch_id = str(uuid.uuid4())
    # Offload inference to background
    background_tasks.add_task(
        run_inference,
        batch_id=batch_id,
        file_name=file.filename,
        df_inference=df,
        parallel=parallel,
    )
    
    return {
        "batch_id": batch_id,
        "file_name": file.filename,
        "status": "PENDING",
        "message": "Inference job started in background."
    }

