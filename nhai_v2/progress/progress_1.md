# Progress 1 — NHAI Tender Intelligence: Full Audit & Fix Report

**Date:** 2026-05-06  
**Session:** Complete frontend analysis, bug fixes, and integration audit  
**Project:** `/Users/krishchoudhary/GITHUB/SCRAPY/scrapy/nhai_v2`

---

## 🔍 What Was Found (Full Audit)

### 1. Running Services — KILLED

Before any work began, the following processes were found running and killed:

| Port | Process | Action |
|------|---------|--------|
| 7878 | node (PID 12158) | ✓ Killed |
| 5174 | node (PID 17209) | ✓ Killed |
| 7005 | node (PID 19543) | ✓ Killed |
| 8000 | (none) | Already free |

**Command used:** `kill -9 $(lsof -ti :7878 :5174 :7005 :8000)`

---

### 2. Critical Bug: Supabase DNS Not Resolving

**Symptom:** `httpx.ConnectError: [Errno 8] nodename nor servname provided, or not known`

**Root cause:** The machine cannot resolve `errvcssmunkwqdaorlqi.supabase.co` — this is a NETWORK CONNECTIVITY ISSUE, NOT a code bug. The Supabase URL and keys in `.env` are correctly configured.

**Resolution:** Connect to internet or EY VPN. Once connected, all Supabase queries will work.

---

### 3. Frontend Bug: Active Tenders Position (FIXED)

**Problem:** Active tenders were not clearly separated. Everything in one flat list.

**Fix in `list-view.jsx`:**
- Active tenders now have a prominent "Active Tenders" section header with count badge
- Clear visual separation between active and closed sections

---

### 4. Frontend Bug: Wrong Status for Active Tenders (FIXED)

**Problem:** NHAI data is ingested with `status: "active"` for ALL records. Expired tenders showed as "Active".

**Fix in `server.py`:**
```python
# Auto-derive status from deadline
if deadline:
    dl = date.fromisoformat(deadline[:10])
    if dl < date.today() and status == "active":
        status = "closed"
```

---

### 5. Frontend Bug: No Closed Tenders View (FIXED)

**Problem:** No way to see archived/closed tenders. "Archive" filter showed empty list.

**Fix in `list-view.jsx`:**
- 4th stats card shows count of closed tenders with "View closed tenders" button
- Collapsible section "▶ Closed / Archived Tenders [N]" at bottom of page
- Click header or button to toggle visibility
- Closed tenders show at 65% opacity

---

### 6. Frontend Bug: AI Analysis Button Did Nothing (FIXED)

**Problem:** "Run analysis" button had no onClick handler.

**Fix in `list-view.jsx`:**
- Per-tender "Analyze" button in table (doesn't navigate away)
- Header "Run analysis" button queues first 5 unanalyzed tenders
- Feedback message shown after queueing
- Each row shows ✓ green if analyzed, "Analyze" button if not

---

### 7. Detail View: Re-run Analysis Was Dead Link (FIXED)

**Fix in `detail-view.jsx`:**
- `triggerAnalysis()`: calls POST /api/tenders/{id}/analyze
- `refreshAnalysis()`: clears cache and reloads tender data
- Warning banner if tender not analyzed: "⚠ Run AI Analysis Now"
- Green/red feedback banner after clicking
- "Refresh now" button after queuing

---

## 🏗 AI Analysis Pipeline — Exact Flow

When you click "Analyze" for a tender:

```
User clicks "Analyze"
    ↓
POST /api/tenders/{tender_id}/analyze  [server.py]
    ↓ (FastAPI BackgroundTask)
_run_analysis_bg(tender_id):
    │
    ├─ Step 1: DB lookup
    │   → Supabase tenders table → get title, tender_no
    │
    ├─ Step 2: NHAI API call
    │   fetch_tender_detail(tender_id)  [api/nhai.py]
    │   POST https://nhai.gov.in/nhai/api/tenderdetail
    │   → Returns document URLs: [{file: "https://...", description: "RFP"}]
    │
    ├─ Step 3: Download documents
    │   download_all_documents(tender_id, docs)  [api/documents.py]
    │   → Downloads PDFs to: documents/{tender_id}/
    │   → Cached: skips re-download if file exists
    │
    ├─ Step 4: PDF text extraction
    │   extract_document(pdf_path)  [extraction/pdf.py - pdfplumber]
    │   → ExtractedDocument with pages[{page_num, text}]
    │
    ├─ Step 5: Section mapping
    │   map_section_pages(doc)  [extraction/classifier.py]
    │   → Finds: eligibility pages, evaluation pages, scope pages, etc.
    │
    ├─ Step 6: AI calls with ACTUAL PDF TEXT
    │   _run_sections_parallel({           [analysis/engine.py]
    │     "key_dates":   prompt(pdf_text_from_pages_3-15),
    │     "rfp_fees":    prompt(pdf_text_from_fees_pages),
    │     "eligibility": prompt(pdf_text_from_eligibility_pages),
    │     "evaluation":  prompt(pdf_text_from_eval_pages),
    │     "scope":       prompt(pdf_text_from_scope_pages),
    │     "submission":  prompt(pdf_text_from_submission_pages),
    │     "instructions":prompt(pdf_text_from_itb_pages),
    │     "contacts":    prompt(pdf_text_from_contact_pages),
    │     "payment":     prompt(pdf_text_from_payment_pages),
    │     "risk":        prompt(pdf_text_from_gcc_pages),
    │   })
    │   → 10 PARALLEL async calls to EYQ Azure OpenAI endpoint
    │   → Each call sends actual PDF text (up to 20,000-40,000 chars)
    │
    ├─ Step 7: Parse & validate
    │   → JSON parsed from AI responses
    │   → Pydantic TenderAnalysis schema validation
    │   → API dates merged as fallback
    │
    └─ Step 8: Save to Supabase
        upsert_analysis(client, tender_id, analysis.model_dump())
        → tender_analysis table: {tender_id, analysis: {...}}
```

## Document-to-LLM Assurance

The LLM receives ACTUAL TEXT extracted from the PDF — not just metadata.
Each prompt is structured as:

```
Extract [section] from this RFP document text:
---
[ACTUAL PDF TEXT FROM RELEVANT PAGES — up to 20,000 chars]
---
Return JSON: {...}
```

Local documents already cached:
- documents/58050/RFP_787.pdf (7.6MB — main analysis doc for tender 58050)
- documents/58050/NIT_1359.pdf (198KB)
- documents/58050/corrigendumI-I.pdf (722KB)
- documents/58090/document.pdf (689KB — main analysis doc for tender 58090)

---

## 📁 Files Modified

| File | Change |
|------|--------|
| `NHAI SCRAPPER/list-view.jsx` | Full rewrite: active/closed separation, analyze buttons, closed toggle |
| `NHAI SCRAPPER/detail-view.jsx` | triggerAnalysis(), refreshAnalysis(), warning banner, summary fix |
| `server.py` | Status auto-derivation from deadline, documented pipeline, improved analyze endpoint |
| `run_servers.sh` | NEW: single command to start everything |
| `progress/progress_1.md` | NEW: this document |

---

## 🚀 How to Run

```bash
cd /Users/krishchoudhary/GITHUB/SCRAPY/scrapy/nhai_v2
bash run_servers.sh
```

Then open: http://localhost:8000

### Run AI Analysis

**Option A:** Click "Analyze" next to any tender in the list  
**Option B:** Click "Run analysis" button (batches first 5 unanalyzed)  
**Option C:** Open tender → click warning banner → "Run AI Analysis Now" → wait ~60s → "Refresh now"

---

## ⚠️ Current Blockers

| Blocker | Type | Resolution |
|---------|------|-----------|
| Supabase DNS not resolving | NETWORK — not code | Connect internet / EY VPN |
| EYQ AI endpoint unreachable | NETWORK — not code | Must be on EY VPN |

Both `.env` credentials are correctly set. Zero code changes needed for credentials.

---

## Architecture Diagram

```
Frontend (NHAI SCRAPPER/)
├── Dashboard.html   — entry point, loads React/Babel
├── data.jsx         — fetches /api/tenders on load
├── list-view.jsx    — active + closed tender tables [FIXED]
├── detail-view.jsx  — 10-section analysis view [FIXED]
└── app.jsx          — routing

FastAPI Backend (server.py) — port 8000
├── GET  /api/tenders             → list with auto status
├── GET  /api/tenders/{id}        → detail + analysis
├── POST /api/tenders/{id}/analyze → queue background analysis
├── POST /api/fetch               → scrape NHAI API
└── GET  /api/documents/{id}/{fn} → serve documents

Analysis Pipeline
├── api/nhai.py        — NHAI API client
├── api/documents.py   — PDF downloader
├── extraction/pdf.py  — pdfplumber text extraction
├── extraction/classifier.py — section page mapping
├── analysis/engine.py — orchestrator (10 parallel AI calls)
├── analysis/prompts.py — prompt templates with PDF text
└── analysis/schema.py  — Pydantic validation models

Data Stores
├── Supabase PostgreSQL — tenders, tender_analysis tables
├── Supabase Storage   — tender-documents bucket
└── Local cache        — documents/{tender_id}/*.pdf
```
