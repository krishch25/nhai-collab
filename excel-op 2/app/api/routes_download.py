"""Download endpoint for classified batches."""

from __future__ import annotations

import io
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.classification_service import get_classified_dataframe_for_batch
from app.services.excel_service import write_classified_excel

router = APIRouter(prefix="/download", tags=["download"])


@router.get("/{batch_id}")
async def download_classified(batch_id: str, db: Annotated[Session, Depends(get_db)] = None):
    """
    Return the classified Excel file for a given batch_id.

    If no classifications are found, returns 404.
    """
    df = get_classified_dataframe_for_batch(db, batch_id)
    if df.empty:
        raise HTTPException(404, f"No classified rows found for batch_id={batch_id}")

    excel_bytes = write_classified_excel(df)  # type: ignore[assignment]
    assert isinstance(excel_bytes, (bytes, bytearray))

    file_like = io.BytesIO(excel_bytes)
    headers = {
        "Content-Disposition": f'attachment; filename="classified_{batch_id}.xlsx"'
    }
    return StreamingResponse(
        file_like,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )

