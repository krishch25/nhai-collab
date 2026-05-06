"""
Supabase operations: upsert tenders, store analysis, upload documents.

Expected tables (run migrations/schema.sql to create):
  tenders          — raw tender metadata from NHAI API
  tender_analysis  — full structured analysis JSON per tender
  tender_documents — per-document metadata + Supabase storage path

Supabase Storage bucket: tender-documents
"""
import json
import logging
from pathlib import Path
from typing import Optional

from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY

log = logging.getLogger(__name__)

STORAGE_BUCKET = "tender-documents"


def get_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)


# ── Tenders ──────────────────────────────────────────────────────────────────

def upsert_tender(client: Client, tender: dict) -> None:
    """Insert or update tender metadata row."""
    client.table("tenders").upsert(tender, on_conflict="tender_id").execute()


def upsert_tenders_bulk(client: Client, tenders: list[dict]) -> None:
    if not tenders:
        return
    client.table("tenders").upsert(tenders, on_conflict="tender_id").execute()
    log.info("Upserted %d tenders", len(tenders))


def get_tender(client: Client, tender_id: str) -> Optional[dict]:
    r = client.table("tenders").select("*").eq("tender_id", tender_id).single().execute()
    return r.data


def list_tenders(client: Client, status: Optional[str] = None) -> list[dict]:
    q = client.table("tenders").select("*").order("submission_deadline", desc=False)
    if status:
        q = q.eq("status", status)
    return q.execute().data or []


# ── Analysis ─────────────────────────────────────────────────────────────────

def upsert_analysis(client: Client, tender_id: str, analysis_dict: dict) -> None:
    """Store full analysis JSON. Overwrites previous analysis for same tender_id."""
    client.table("tender_analysis").upsert(
        {"tender_id": tender_id, "analysis": analysis_dict},
        on_conflict="tender_id",
    ).execute()
    log.info("Analysis saved for tender %s", tender_id)


def get_analysis(client: Client, tender_id: str) -> Optional[dict]:
    """Returns analysis dict or None — never raises on missing row."""
    try:
        r = (client.table("tender_analysis")
             .select("analysis")
             .eq("tender_id", tender_id)
             .maybe_single()   # returns None instead of raising PGRST116
             .execute())
        return r.data.get("analysis") if r.data else None
    except Exception as e:
        log.warning("get_analysis(%s) error: %s", tender_id, e)
        return None



# ── Documents ────────────────────────────────────────────────────────────────

def upload_document(client: Client, local_path: Path, tender_id: str) -> str:
    """
    Upload document to Supabase Storage.
    Returns the storage path (tender_id/filename).
    """
    storage_path = f"{tender_id}/{local_path.name}"
    with open(local_path, "rb") as f:
        content = f.read()

    # upsert=True overwrites if already exists
    client.storage.from_(STORAGE_BUCKET).upload(
        path=storage_path,
        file=content,
        file_options={"upsert": "true"},
    )
    log.info("Uploaded %s → %s", local_path.name, storage_path)
    return storage_path


def get_document_url(client: Client, storage_path: str) -> str:
    """Get public URL for a stored document."""
    return client.storage.from_(STORAGE_BUCKET).get_public_url(storage_path)


def upsert_document_metadata(client: Client, tender_id: str, doc: dict) -> None:
    client.table("tender_documents").upsert(
        {**doc, "tender_id": tender_id},
        on_conflict="tender_id,filename",
    ).execute()
