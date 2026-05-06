"""
NHAI Tender Intelligence — FastAPI server.
"""
import re
import sys
import logging
import asyncio
from pathlib import Path
from typing import Optional
from datetime import date

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from db.supabase import get_client, list_tenders, get_analysis, upsert_analysis
from config import SUPABASE_URL, SUPABASE_KEY

log = logging.getLogger(__name__)
app = FastAPI(title="NHAI Tender Intelligence")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

FRONTEND_DIR = Path(__file__).parent / "NHAI SCRAPPER"

_NH_RE = re.compile(r'\bNH[- ]?\d+[A-Za-z]?\b', re.IGNORECASE)
_KM_RE = re.compile(r'km\.?\s*([\d.]+)\s*to\s*km\.?\s*([\d.]+)', re.IGNORECASE)
_STATES = {
    "rajasthan","maharashtra","karnataka","gujarat","haryana","punjab",
    "uttar pradesh","madhya pradesh","bihar","west bengal","assam",
    "tamil nadu","andhra pradesh","telangana","odisha","jharkhand",
    "himachal pradesh","uttarakhand","chhattisgarh","kerala","goa",
    "jammu","kashmir","manipur","meghalaya","nagaland","tripura",
    "arunachal pradesh","mizoram","sikkim","delhi","chandigarh",
}


def _parse_title(title: str) -> dict:
    nhs = _NH_RE.findall(title)
    nh = nhs[0].upper().replace(" ", "-") if nhs else "N/A"
    km_match = _KM_RE.search(title)
    if km_match:
        start, end = float(km_match.group(1)), float(km_match.group(2))
        chainage = f"km {start:.3f} to km {end:.3f}"
        length = round(abs(end - start), 2)
    else:
        chainage, length = "N/A", 0
    state = "N/A"
    for word in _STATES:
        if word in title.lower():
            state = word.title()
            break
    return {"nh": nh, "state": state, "chainage": chainage, "length": length}


def _compute_status(t: dict) -> str:
    deadline = t.get("submission_deadline", "")
    status = t.get("status", "active")
    if deadline:
        try:
            if date.fromisoformat(deadline[:10]) < date.today():
                status = "closed"
        except Exception:
            pass
    return status


def _ef() -> dict:
    """Empty field — N/A with no page citation."""
    return {"value": "N/A", "page": 0, "snippet": ""}


def _tender_to_list_item(t: dict, analysis: Optional[dict], is_analyzed: bool) -> dict:
    parsed = _parse_title(t.get("title", ""))
    raw = t.get("raw_detail") or {}
    tender_type = "unknown"
    if is_analyzed and analysis:
        tender_type = analysis.get("tender_type", "unknown")
    elif raw.get("tender_type"):
        tender_type = raw["tender_type"].lower()

    rfp_fee = emd = est_value = 0
    if is_analyzed and analysis:
        fees = analysis.get("rfp_fees", {})
        for key, var in [("rfp_fee_amount", "rfp_fee"), ("emd_amount", "emd")]:
            m = re.search(r'[\d,]+', str(fees.get(key, "")).replace(" ", ""))
            if m:
                val = int(m.group(0).replace(",", ""))
                if key == "rfp_fee_amount":
                    rfp_fee = val
                else:
                    emd = val

    spoc = "N/A"
    duration = "N/A"
    docs = 0
    if is_analyzed and analysis:
        contacts = analysis.get("contacts", [])
        if contacts:
            spoc = contacts[0].get("name", "N/A")
        duration = analysis.get("scope", {}).get("contract_duration", "N/A")
        docs = len(analysis.get("documents", []))

    return {
        "id":        t["tender_id"],
        "no":        t.get("tender_no", ""),
        "title":     t.get("title", ""),
        "state":     parsed["state"],
        "nh":        parsed["nh"],
        "chainage":  parsed["chainage"],
        "length":    parsed["length"],
        "type":      tender_type,
        "method":    raw.get("evaluation_type", "N/A"),
        "status":    _compute_status(t),
        "publish":   (t.get("publish_date") or "")[:10],
        "deadline":  t.get("submission_deadline", ""),
        "bidOpen":   t.get("bid_opening_date", ""),
        "rfpFee":    rfp_fee,
        "emd":       emd,
        "estValue":  est_value,
        "duration":  duration,
        "confidence": analysis.get("confidence", "low") if (is_analyzed and analysis) else "low",
        "match":     0,
        "docs":      docs,
        "pages":     0,
        "spoc":      spoc,
        "analyzed":  is_analyzed,
    }


def _analysis_to_detail(t: dict, analysis: dict) -> dict:
    base = _tender_to_list_item(t, analysis, True)
    kd   = analysis.get("key_dates", {}) or {}
    fees = analysis.get("rfp_fees", {}) or {}
    elig = analysis.get("eligibility", {}) or {}
    ev   = analysis.get("evaluation", {}) or {}
    sc   = analysis.get("scope", {}) or {}
    sub  = analysis.get("submission", {}) or {}
    contacts = analysis.get("contacts", []) or []
    payment  = analysis.get("payment_terms", []) or []
    risk = analysis.get("risk", {}) or {}
    docs = analysis.get("documents", []) or []

    def cite(src):
        if not src or not isinstance(src, list): return {}
        c = src[0] if isinstance(src[0], dict) else {}
        return {"page": c.get("page", 0), "snippet": c.get("snippet", "")}

    def field(obj, key, src_key=None):
        v = obj.get(key) or "N/A"
        r = {"value": v}
        if src_key:
            r.update(cite(obj.get(src_key, [])))
        return r

    def kdf(k): return field(kd, k, f"{k}_source")

    tech = elig.get("technical", {}) or {}
    fin  = elig.get("financial", {}) or {}
    bd   = fees.get("bank_details", {}) or {}

    bank = {
        "beneficiary": bd.get("beneficiary_name", bd.get("beneficiary", "N/A")),
        "account":     bd.get("account_number",   bd.get("account", "N/A")),
        "ifsc":        bd.get("ifsc_code",         bd.get("ifsc", "N/A")),
        "bank":        bd.get("bank_name",         bd.get("bank", "N/A")),
        "page":        bd.get("page", 0),
        "snippet":     bd.get("snippet", ""),
    }

    kp_page = cite(tech.get("key_personnel_source", [])).get("page", 0)
    key_personnel = []
    for kp in tech.get("key_personnel_requirements", []):
        if isinstance(kp, dict):
            key_personnel.append({"role": kp.get("role",""), "years": kp.get("years",""), "page": kp.get("page", kp_page)})
        else:
            key_personnel.append({"role": str(kp), "years": "", "page": kp_page})

    forms = []
    for f in sub.get("required_forms", []):
        forms.append({
            "id":        f.get("form_number", f.get("id", "")),
            "name":      f.get("form_name",   f.get("name", "")),
            "auth":      f.get("signing_authority", f.get("auth", "N/A")),
            "mandatory": f.get("mandatory", True),
            "page":      f.get("source_page", f.get("page", 0)),
        })

    def scope_items(lst):
        out = []
        for s in (lst or []):
            if isinstance(s, dict):
                pg = (s.get("source") or [{}])[0].get("page", 0) if s.get("source") else s.get("page", 0)
                out.append({"d": s.get("description", s.get("d", "")), "page": pg})
            else:
                out.append({"d": str(s), "page": 0})
        return out

    def scope_deliv(lst):
        out = []
        for d in (lst or []):
            if isinstance(d, dict):
                pg = (d.get("source") or [{}])[0].get("page", 0) if d.get("source") else d.get("page", 0)
                out.append({"name": d.get("description", d.get("name","")), "timeline": d.get("timeline",""), "page": pg})
            else:
                out.append({"name": str(d), "timeline": "", "page": 0})
        return out

    tw = ev.get("technical_weightage", "N/A")
    fw = ev.get("financial_weightage", "N/A")
    formula = (f"Composite = {tw} × Technical + {fw} × Financial"
               if tw and tw != "N/A" else ev.get("evaluation_formula", "Per RFP methodology"))

    return {
        **base,
        "summary":       sc.get("summary", "N/A") or "N/A",
        "sourcePdf":     docs[0].get("filename", "") if docs else "",
        "pdfTotalPages": 0,
        "key_dates": {
            "pre_bid_meeting":              kdf("pre_bid_meeting"),
            "last_date_clarification":      kdf("last_date_clarification"),
            "proposal_submission_deadline": kdf("proposal_submission_deadline"),
            "technical_bid_opening":        kdf("technical_bid_opening"),
            "financial_bid_opening":        kdf("financial_bid_opening"),
            "bid_validity":                 field(kd, "bid_validity_period",      "bid_validity_period_source"),
            "document_download":            field(kd, "document_download_period", "document_download_period_source"),
        },
        "rfp_fees": {
            "rfp_fee_amount":       field(fees, "rfp_fee_amount",       "rfp_fee_source"),
            "payment_mode":         {"value": fees.get("payment_mode", "N/A")},
            "bank":                 bank,
            "emd_amount":           field(fees, "emd_amount",           "emd_source"),
            "performance_security": field(fees, "performance_security", "performance_security_source"),
        },
        "eligibility": {
            "technical": {
                "min_annual_turnover":        field(tech, "min_annual_turnover",       "min_annual_turnover_source"),
                "similar_project_experience": field(tech, "similar_project_experience","similar_project_experience_source"),
                "jv":                         field(tech, "jv_conditions",             "jv_conditions_source"),
                "ongoing_cap":                field(tech, "ongoing_assignment_cap",    "ongoing_assignment_cap_source"),
                "key_personnel":              key_personnel,
                "other_conditions":           tech.get("other_conditions", []),
            },
            "financial": {
                "min_annual_turnover": field(fin, "min_annual_turnover",        "min_annual_turnover_source"),
                "net_worth":           field(fin, "net_worth_requirement",      "net_worth_requirement_source"),
                "financial_years":     field(fin, "financial_years_considered", "financial_years_considered_source"),
                "other_conditions":    fin.get("other_conditions", []),
            },
        },
        "evaluation": {
            "method":                   field(ev, "selection_method",              "selection_method_source"),
            "technical_weight":         {"value": tw},
            "financial_weight":         field(ev, "financial_weightage",           "weightage_source"),
            "technical_min_qualifying": field(ev, "technical_min_qualifying_score","qualifying_score_source"),
            "formula":                  formula,
            "criteria": [
                {"criterion": c.get("criterion",""), "marks": c.get("max_marks","N/A"), "page": 0}
                for c in ev.get("technical_evaluation_criteria", []) if isinstance(c, dict)
            ],
            "pass_fail":             ev.get("pass_fail_criteria", []),
            "financial_higher_wins": ev.get("financial_higher_wins", False),
        },
        "scope": {
            "summary":           sc.get("summary", "N/A") or "N/A",
            "location":          field(sc, "project_location",  "project_location_source"),
            "contract_duration": field(sc, "contract_duration", "contract_duration_source"),
            "in_scope":          scope_items(sc.get("in_scope", [])),
            "out_of_scope":      scope_items(sc.get("out_of_scope", [])),
            "deliverables":      scope_deliv(sc.get("deliverables", [])),
            "milestones":        sc.get("milestones", []),
            "client_obligations":scope_items(sc.get("client_obligations", [])),
        },
        "submission": {
            "mode":           field(sub, "submission_mode", "submission_mode_source"),
            "portal":         field(sub, "portal",           "portal_source"),
            "forms":          forms,
            "certifications": sub.get("certifications_required", []),
            "annexures":      sub.get("annexures_required", []),
            "copies":         {"value": sub.get("number_of_copies", "N/A")},
            "language":       {"value": sub.get("language", "N/A")},
        },
        "contact":      contacts[0] if contacts else {},
        "all_contacts": contacts,
        "payment": [
            {"milestone": p.get("milestone",""), "pct": p.get("percentage",""),
             "cond": p.get("condition",""), "page": (p.get("source") or [{}])[0].get("page",0)}
            for p in payment
        ],
        "risk": {
            "liquidated_damages": field(risk, "liquidated_damages", "liquidated_damages_source"),
            "force_majeure":      field(risk, "force_majeure",       "force_majeure_source"),
            "termination":        risk.get("termination_conditions", []),
            "dispute":            field(risk, "dispute_resolution",  "dispute_resolution_source"),
            "integrity_pact":     field(risk, "integrity_pact",      "integrity_pact_source"),
            "insurance":          risk.get("insurance_requirements", []),
            "penalty_clauses":    risk.get("penalty_clauses", []),
        },
        "documents": [
            {"filename": d.get("filename",""), "description": d.get("description",""),
             "filesize": d.get("filesize",""), "url": d.get("url",""),
             "supabase_path": d.get("supabase_path",""), "is_form": d.get("is_form", False),
             "extension": d.get("extension","")}
            for d in docs
        ],
    }


def _unanalyzed_detail(t: dict) -> dict:
    """Full detail structure for a tender with no analysis yet. Never crashes the frontend."""
    base = _tender_to_list_item(t, None, False)
    ef = _ef
    return {
        **base,
        "summary":       "Analysis not yet run. Click 'Run AI Analysis' to extract all details from the tender document.",
        "sourcePdf":     "",
        "pdfTotalPages": 0,
        "key_dates": {
            "pre_bid_meeting":              ef(),
            "last_date_clarification":      ef(),
            "proposal_submission_deadline": {"value": t.get("submission_deadline","N/A"), "page": 0, "snippet": ""},
            "technical_bid_opening":        {"value": t.get("bid_opening_date","N/A"), "page": 0, "snippet": ""},
            "financial_bid_opening":        ef(),
            "bid_validity":                 ef(),
            "document_download":            ef(),
        },
        "rfp_fees": {
            "rfp_fee_amount":       ef(),
            "payment_mode":         {"value": "N/A"},
            "bank":                 {"beneficiary":"N/A","account":"N/A","ifsc":"N/A","bank":"N/A","page":0,"snippet":""},
            "emd_amount":           ef(),
            "performance_security": ef(),
        },
        "eligibility": {
            "technical":  {"min_annual_turnover":ef(),"similar_project_experience":ef(),"jv":ef(),"ongoing_cap":ef(),"key_personnel":[],"other_conditions":[]},
            "financial":  {"min_annual_turnover":ef(),"net_worth":ef(),"financial_years":ef(),"other_conditions":[]},
        },
        "evaluation": {
            "method":ef(),"technical_weight":{"value":"N/A"},"financial_weight":ef(),
            "technical_min_qualifying":ef(),"formula":"N/A","criteria":[],"pass_fail":[],"financial_higher_wins":False,
        },
        "scope": {
            "summary":"N/A","location":ef(),"contract_duration":ef(),
            "in_scope":[],"out_of_scope":[],"deliverables":[],"milestones":[],"client_obligations":[],
        },
        "submission": {
            "mode":ef(),"portal":ef(),"forms":[],"certifications":[],"annexures":[],"copies":{"value":"N/A"},"language":{"value":"N/A"},
        },
        "contact": {}, "all_contacts": [],
        "payment": [],
        "risk": {
            "liquidated_damages":ef(),"force_majeure":ef(),"termination":[],"dispute":ef(),"integrity_pact":ef(),"insurance":[],"penalty_clauses":[],
        },
        "documents": [],
    }


# ── Auto-analysis queue ───────────────────────────────────────────────────────

_analysis_queue: set = set()  # tender_ids currently being analyzed


def _run_analysis_bg(tender_id: str):
    """Full pipeline: fetch NHAI API → download PDFs → extract text → AI → save."""
    if tender_id in _analysis_queue:
        return
    _analysis_queue.add(tender_id)
    try:
        from api.nhai import fetch_tender_detail
        from api.documents import download_all_documents
        from analysis.engine import analyze_tender

        client = get_client()
        row = client.table("tenders").select("title,tender_no").eq("tender_id", tender_id).single().execute().data or {}
        log.info("[%s] ► Analyzing: %s", tender_id, row.get("title","")[:60])

        detail = fetch_tender_detail(tender_id)
        other_docs = detail.get("other_documents", [])
        log.info("[%s] Found %d documents", tender_id, len(other_docs))

        downloaded = download_all_documents(tender_id, other_docs)
        pdf_count = sum(1 for d in downloaded if d.get("extension") == ".pdf" and not d.get("error"))
        log.info("[%s] Downloaded %d files (%d PDFs)", tender_id, len(downloaded), pdf_count)

        analysis = analyze_tender(
            tender_id=tender_id,
            tender_no=row.get("tender_no", ""),
            title=row.get("title", detail.get("title", "")),
            downloaded_docs=downloaded,
            api_detail=detail,
        )
        upsert_analysis(client, tender_id, analysis.model_dump())
        log.info("[%s] ✓ Done — confidence=%s", tender_id, analysis.confidence)
    except Exception as e:
        log.error("[%s] ✗ Analysis failed: %s", tender_id, e, exc_info=True)
    finally:
        _analysis_queue.discard(tender_id)


def _auto_analyze_active(client):
    """Sequentially analyze all unanalyzed active tenders. One at a time with delays to avoid 429."""
    import time
    try:
        today = date.today().isoformat()
        active_rows = (client.table("tenders")
                       .select("tender_id,submission_deadline,title")
                       .gte("submission_deadline", today)
                       .execute().data or [])
        active_ids = {r["tender_id"] for r in active_rows}
        if not active_ids:
            log.info("Auto-analyze: no active tenders found")
            return

        analyzed_rows = (client.table("tender_analysis")
                         .select("tender_id")
                         .execute().data or [])
        analyzed_ids = {r["tender_id"] for r in analyzed_rows}

        to_analyze = sorted(active_ids - analyzed_ids)
        log.info("Auto-analyze: %d active, %d analyzed, %d queued for analysis",
                 len(active_ids), len(analyzed_ids), len(to_analyze))

        if not to_analyze:
            log.info("Auto-analyze: all active tenders are already analyzed ✓")
            return

        # Wait 10s for server to fully start
        time.sleep(10)

        for i, tid in enumerate(to_analyze):
            log.info("Auto-analyze: [%d/%d] starting %s", i+1, len(to_analyze), tid)
            _run_analysis_bg(tid)  # run synchronously — waits for completion
            if i < len(to_analyze) - 1:
                # 60s gap between tenders to respect rate limits
                log.info("Auto-analyze: waiting 60s before next tender...")
                time.sleep(60)

        log.info("Auto-analyze: complete — analyzed %d tenders", len(to_analyze))
    except Exception as e:
        log.error("Auto-analyze startup failed: %s", e)



# ── API routes ────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def on_startup():
    """Auto-analyze all unanalyzed active tenders when server starts."""
    import threading
    def _bg():
        try:
            client = get_client()
            _auto_analyze_active(client)
        except Exception as e:
            log.error("Startup auto-analyze error: %s", e)
    threading.Thread(target=_bg, daemon=True).start()


@app.get("/api/tenders")
async def api_tenders():
    client = get_client()
    tenders = list_tenders(client)
    analyzed_rows = client.table("tender_analysis").select("tender_id, analysis").execute().data or []
    analyzed_map = {r["tender_id"]: r.get("analysis") for r in analyzed_rows}
    result = [_tender_to_list_item(t, analyzed_map.get(t["tender_id"]), t["tender_id"] in analyzed_map)
              for t in tenders]
    return JSONResponse(result)


@app.get("/api/tenders/{tender_id}")
async def api_tender_detail(tender_id: str):
    """Always returns full nested structure — never crashes the frontend."""
    client = get_client()
    row = client.table("tenders").select("*").eq("tender_id", tender_id).single().execute()
    if not row.data:
        raise HTTPException(status_code=404, detail="Tender not found")
    analysis = get_analysis(client, tender_id)
    if analysis:
        return JSONResponse(_analysis_to_detail(row.data, analysis))
    # No analysis yet — return full structure with N/A values + auto-queue analysis
    import threading
    threading.Thread(target=_run_analysis_bg, args=(tender_id,), daemon=True).start()
    return JSONResponse(_unanalyzed_detail(row.data))


@app.get("/api/analysis_status")
async def api_analysis_status():
    """Returns which tender_ids are currently being analyzed."""
    return JSONResponse({"analyzing": list(_analysis_queue)})


@app.post("/api/tenders/{tender_id}/analyze")
async def api_analyze(tender_id: str, background_tasks: BackgroundTasks):
    client = get_client()
    row = client.table("tenders").select("tender_id").eq("tender_id", tender_id).single().execute()
    if not row.data:
        raise HTTPException(status_code=404, detail=f"Tender {tender_id} not found")
    background_tasks.add_task(_run_analysis_bg, tender_id)
    return {"status": "queued", "tender_id": tender_id}


@app.post("/api/fetch")
async def api_fetch_tenders(background_tasks: BackgroundTasks):
    """Fetch latest tenders from NHAI API, save to Supabase, auto-analyze new ones."""
    from api.nhai import fetch_tender_list
    from db.supabase import upsert_tenders_bulk
    from datetime import datetime, timezone

    client = get_client()
    raw = fetch_tender_list(page_size=10000)

    # Get existing tender IDs
    existing = {r["tender_id"] for r in
                (client.table("tenders").select("tender_id").execute().data or [])}

    rows = [{
        "tender_id":           str(t.get("id", "")),
        "tender_no":           t.get("tender_no", ""),
        "title":               t.get("title", ""),
        "publish_date":        t.get("publish_date", ""),
        "submission_deadline": t.get("bid_submission_end_date", ""),
        "bid_opening_date":    t.get("bid_opening_date", ""),
        "source_url":          "https://nhai.gov.in/#/tenders",
        "status":              "active",
        "fetched_at":          datetime.now(timezone.utc).isoformat(),
        "raw_detail":          {},
    } for t in raw]
    upsert_tenders_bulk(client, rows)

    # Auto-queue analysis for NEW active tenders only
    new_ids = [r["tender_id"] for r in rows if r["tender_id"] not in existing]
    for tid in new_ids:
        background_tasks.add_task(_run_analysis_bg, tid)

    return {"fetched": len(rows), "new": len(new_ids), "analysis_queued": len(new_ids)}


@app.get("/api/documents/{tender_id}/{filename}")
async def api_document(tender_id: str, filename: str):
    from config import DOCS_DIR
    local = DOCS_DIR / tender_id / filename
    if local.exists():
        mt = "application/pdf" if filename.endswith(".pdf") else "application/octet-stream"
        return FileResponse(str(local), media_type=mt,
                            headers={"Content-Disposition": f'inline; filename="{filename}"',
                                     "Cache-Control": "max-age=3600"})
    client = get_client()
    try:
        data = client.storage.from_("tender-documents").download(f"{tender_id}/{filename}")
        mt = "application/pdf" if filename.endswith(".pdf") else "application/octet-stream"
        return Response(content=data, media_type=mt,
                        headers={"Content-Disposition": f'inline; filename="{filename}"'})
    except Exception:
        raise HTTPException(status_code=404, detail="Document not found")


@app.get("/")
async def root():
    return FileResponse(str(FRONTEND_DIR / "Dashboard.html"))

app.mount("/", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)

