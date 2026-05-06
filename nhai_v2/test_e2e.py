#!/usr/bin/env python3
import json
import logging
import sys
import time
from pathlib import Path

# Insert local path
sys.path.insert(0, str(Path(__file__).parent))

from api.nhai import fetch_tender_list, fetch_tender_detail
from api.documents import download_all_documents
from analysis.engine import analyze_tender
from db.supabase import get_client, upsert_tenders_bulk, upsert_analysis, upload_document, upsert_document_metadata
from cli import _normalize_tender

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger("ToughTestE2E")

def run_tests():
    log.info("Starting End-to-End Tough Testing of NHAI Scraper...")
    client = get_client()

    # --- Phase 1: Mass Ingestion / API Scrape ---
    log.info("Phase 1: Fetching recent tenders (Mass Scrape Test)")
    tenders = []
    try:
        tenders = fetch_tender_list(page_size=20)
        log.info(f"✅ Successfully fetched {len(tenders)} tenders from NHAI API.")
        if len(tenders) == 0:
            log.error("❌ Failed to fetch any tenders. Aborting test.")
            return
            
        rows = [_normalize_tender(t) for t in tenders]
        upsert_tenders_bulk(client, rows)
        log.info(f"✅ Successfully ingested {len(rows)} normalized tenders into Supabase 'tenders' table.")
    except Exception as e:
        log.error(f"❌ Mass scrape failed: {e}")
        return

    # --- Phase 2: Pick a target for deep analysis ---
    # We will pick the first one that has "other_documents" if possible, or just the first one.
    target_tender = tenders[0]
    tender_id = str(target_tender.get("id"))
    tender_no = target_tender.get("tender_no", "")
    title = target_tender.get("title", "")
    
    log.info(f"\nPhase 2: Deep Analysis on Tender ID: {tender_id} ({tender_no})")
    
    # 2a: Detail API
    detail_data = {}
    try:
        detail_data = fetch_tender_detail(tender_id)
        log.info(f"✅ Successfully fetched details. Found {len(detail_data.get('other_documents', []))} documents.")
    except Exception as e:
        log.error(f"❌ Failed to fetch detail API: {e}")

    # 2b: Document Download
    other_docs = detail_data.get("other_documents", [])
    downloaded = []
    try:
        downloaded = download_all_documents(tender_id, other_docs)
        success_docs = [d for d in downloaded if not d.get("error")]
        error_docs = [d for d in downloaded if d.get("error")]
        log.info(f"✅ Document download complete: {len(success_docs)} succeeded, {len(error_docs)} failed.")
        for e_doc in error_docs:
            log.warning(f"⚠️ Document error on '{e_doc.get('filename')}': {e_doc.get('error')}")
    except Exception as e:
        log.error(f"❌ Document download process crashed: {e}")

    # 2c: AI Analysis
    analysis_result = None
    try:
        log.info("⏳ Sending data to AI Engine for full structural extraction...")
        start_time = time.time()
        analysis = analyze_tender(
            tender_id=tender_id,
            tender_no=tender_no,
            title=title,
            downloaded_docs=downloaded,
            api_detail=detail_data,
        )
        duration = time.time() - start_time
        analysis_result = analysis.model_dump()
        log.info(f"✅ AI Analysis complete in {duration:.2f} seconds!")
        log.info(f"   Confidence: {analysis.confidence}")
        log.info(f"   Key Dates Parsed: {bool(analysis.key_dates)}")
        
        upsert_analysis(client, tender_id, analysis_result)
        log.info("✅ Analysis JSON successfully saved to Supabase 'tender_analysis' table.")
    except Exception as e:
        log.error(f"❌ AI Analysis pipeline crashed: {e}")

    # 2d: Storage Upload
    if downloaded:
        log.info("\nPhase 3: Testing Supabase Storage Uploads")
        for d in downloaded:
            if d.get("local_path") and not d.get("error"):
                try:
                    path = Path(d["local_path"])
                    storage_path = upload_document(client, path, tender_id)
                    upsert_document_metadata(client, tender_id, {
                        "filename": d["filename"],
                        "description": d.get("description", ""),
                        "url": d["url"],
                        "filesize": d.get("filesize", ""),
                        "extension": d.get("extension", ""),
                        "supabase_path": storage_path,
                    })
                    log.info(f"✅ Uploaded to Storage & metadata synced: {d['filename']}")
                except Exception as e:
                    log.error(f"❌ Storage upload failed for {d['filename']}: {e}")

    log.info("\n==================================================")
    log.info("🎉 E2E TOUGH TESTING COMPLETED")
    log.info("==================================================")
    if analysis_result:
        log.info("AI Extracted Summary Snapshot:")
        log.info(f"  Tender Type: {analysis_result.get('tender_type')}")
        log.info(f"  Selection Method: {analysis_result.get('evaluation', {}).get('selection_method')}")
        log.info(f"  EMD Amount: {analysis_result.get('rfp_fees', {}).get('emd_amount')}")


if __name__ == "__main__":
    run_tests()
