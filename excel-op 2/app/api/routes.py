"""API routes for upload, process, and download."""

import io
import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.services.excel_service import read_inference_excel, read_training_excel

router = APIRouter()


@router.post("/upload/training")
async def upload_training(file: UploadFile = File(...)):
    """Upload Excel with raw material + L0/L1/L2 for training."""
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(400, "Expected .xlsx or .xls file")
    contents = await file.read()
    try:
        df = read_training_excel(io.BytesIO(contents))
    except ValueError as e:
        raise HTTPException(400, str(e))
    batch_id = str(uuid.uuid4())
    return {
        "batch_id": batch_id,
        "rows": len(df),
        "columns": list(df.columns),
        "message": "Training file ingested. Rule generation will run next.",
    }


@router.post("/upload/inference")
async def upload_inference(file: UploadFile = File(...)):
    """Upload Excel with raw material only for inference."""
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(400, "Expected .xlsx or .xls file")
    contents = await file.read()
    df = read_inference_excel(io.BytesIO(contents))
    batch_id = str(uuid.uuid4())
    return {
        "batch_id": batch_id,
        "rows": len(df),
        "columns": list(df.columns),
        "message": "Inference file ingested. Classification will run next.",
    }


@router.get("/download/{batch_id}")
async def download_classified(batch_id: str):
    """Return classified Excel. Placeholder until classification is implemented."""
    raise HTTPException(501, "Classification not yet implemented.")
