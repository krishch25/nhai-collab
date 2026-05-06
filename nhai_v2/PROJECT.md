# NHAI Tender Intelligence System — Technical Architecture & Workflow

**Developer:** Krish Choudhary  
**Organisation:** Ernst & Young — AI Incubator Division  

## Overview
This document provides a comprehensive, up-to-date natural language guide explaining the end-to-end architecture, workflows, and core mechanics of the NHAI Tender Intelligence System. The system is designed to autonomously fetch tenders from the NHAI portal, ingest their attached documents, meticulously parse the text, and query a GPT-based AI endpoint (EYQ) to extract structured, citation-backed intelligence for a dedicated interactive dashboard.

---

## 1. System Architecture & Complete Pipeline Workflow

The platform operates on a robust, asynchronous pipeline built around a Python FastAPI backend, a Supabase PostgreSQL database, and direct integrations with both the NHAI API and the EYQ (GPT) LLM endpoint.

### The Complete Pipeline Structure:
1. **Data Fetching:** The system regularly polls the official NHAI API to retrieve the latest tender list and details.
2. **Document Ingestion:** All associated files (RFPs, NITs, Corrigenda, BOQs) are downloaded to a local cache and simultaneously uploaded to a public Supabase Storage bucket.
3. **Text Extraction & Classification:** The downloaded PDFs are parsed page-by-page. The system intelligently classifies the document type (e.g., "2-stage" vs "single-stage") and maps out relevant keywords to pinpoint which pages contain critical sections (like Eligibility, Scope, or Fees).
4. **Context Building & LLM Querying:** For each section of the tender, the system aggregates the exact pages required, merges supplementary or overriding corrigendum text, and sends this precise context to the LLM.
5. **Data Structuring & Database Storage:** The AI responds with structured JSON that includes exact data points and verbatim citations. This data is rigorously validated via Pydantic schemas and saved into the Supabase database.
6. **Dashboard Delivery:** The FastAPI backend serves this structured data to the interactive dashboard, ensuring it matches the exact schema expected by the frontend (preventing crashes and ensuring accurate visual reporting).

---

## 2. Core Backend Flow & FastAPI Structure

The backend is driven by **FastAPI** (`server.py`), providing both REST API endpoints and background orchestration.

### Key Logic & Functions:
- **Endpoints:** The server exposes routes like `/api/fetch` (to pull latest tenders), `/api/tenders` (to list all ingested tenders for the dashboard), and `/api/tenders/{tender_id}` (for detailed views).
- **Auto-Analysis Queue:** Upon startup, or when new tenders are fetched, an auto-analyze background thread (`_auto_analyze_active`) sequentially kicks off the AI analysis for any active, unanalyzed tenders. It intelligently respects rate limits by pausing between tasks.
- **Dashboard Synchronization:** The API dynamically maps the backend data using `_analysis_to_detail()` and `_unanalyzed_detail()`. This ensures that whether a tender is fully analyzed or still in the queue, the dashboard receives a consistent data structure. Safe defaults (e.g., `N/A`, `0`) are injected, and complex nested data (like Technical/Financial weightages or payment terms) is transformed directly into frontend-friendly lists.

---

## 3. Data Fetching & Pipeline Ingestion

### Fetching Data from NHAI:
The ingestion starts in `api/nhai.py`. The backend sends `POST` requests to the NHAI `tenderlist` and `tenderdetail` APIs. 
- It captures the fundamental metadata: title, tender ID (`nid`), publishing dates, and submission deadlines.
- The details endpoint reveals the direct download links to the tender's attached files.

### The Ingestion Pipeline & Context Saving:
1. **Document Download:** `api/documents.py` downloads all PDFs and supplementary files. They are cached locally in the `documents/` directory.
2. **Supabase Upload:** The documents are mirrored into a Supabase Storage bucket (`tender-documents`), allowing the dashboard to stream or render PDFs inline via public URLs.
3. **Database Upsert:** The raw tender metadata is immediately upserted into the `tenders` database table.
4. **Context Saving:** The local downloaded PDFs serve as the offline text context. The Supabase database serves as the persistent metadata context.

---

## 4. Document Parsing & Context Preparation for the LLM

It is critical that the dashboard receives accurate data. Dumping a 300-page PDF into an LLM would result in hallucinations and token limits. The system solves this via highly targeted parsing:

### Parsing Accuracy & Alignment:
- **Page-by-page Extraction (`extraction/pdf.py`):** `pdfplumber` extracts text while preserving the exact page number (e.g., `[PAGE 15]`).
- **Classification & Mapping (`extraction/classifier.py`):** The system scans for keywords to figure out which pages contain which sections. For example, it searches for "QCBS" or "weightage" to locate the "Evaluation Criteria" section.
- **Document Merging:** If a tender has an RFP, an NIT, and a Corrigendum, the engine seamlessly merges them. Corrigenda are dynamically appended to override outdated rules in the main RFP.

### What Context is Sent to the LLM?
Instead of sending everything, the LLM receives only the "mapped" pages for a specific section (typically 5-15 pages max). If a section's text exceeds the threshold (e.g., 12,000 characters), the system employs a **batched overlapping strategy**. It breaks the section into overlapping chunks, queries the AI for each chunk, and finally prompts the AI to merge the partial JSON results into one authoritative output.

---

## 5. AI Integration: Prompts and Received Analysis

### Sending to the GPT Endpoint (EYQ):
The backend uses parallel async requests (`asyncio.gather`) to query the EYQ endpoint simultaneously for all 10 distinct analytical sections (e.g., Scope, Key Dates, Risk, Fees, Eligibility).

### What Analysis is Received?
The AI endpoint is instructed (via strict prompts in `analysis/prompts.py`) to return **only valid JSON** containing the facts, accompanied by exact page citations and verbatim text snippets.

For example, the GPT endpoint returns data like:
```json
{
  "proposal_submission_deadline": "2026-05-14 at 11:00 hrs",
  "proposal_submission_deadline_source": [
    { "page": 5, "snippet": "The RFP will be invited through e-tendering portal... upto 11:00 hrs" }
  ]
}
```

### Structuring and Pydantic Validation:
Once the JSON is received, it is rigorously validated against strict Pydantic schemas (`analysis/schema.py`). Any hallucinated fields or malformed data types are automatically rejected and safely fall back to default values. This guarantees that the dashboard receives perfectly formatted data every single time.

---

## 6. Database Schema Correctness & Operations

The system uses Supabase PostgreSQL, operating with a clean, normalized relational schema designed for stability.

### Schema Mechanics:
1. **`tenders` Table:** 
   - Acts as the source of truth for raw NHAI metadata. 
   - Uses `tender_id` as the Primary Key. 
   - Handles the active/closed status based on deadlines.
2. **`tender_analysis` Table:** 
   - Stores the final, validated Pydantic JSON dump from the LLM. 
   - Linked to `tenders` via a Foreign Key (`tender_id`). 
   - Using a `JSONB` column here is correct and optimal, as it allows the dashboard to pull the massive nested intelligence report dynamically without requiring dozens of complex SQL joins.
3. **`tender_documents` Table:** 
   - Maps each downloaded file (filename, size, Supabase storage path) to a specific `tender_id`.

**Pipeline Correctness:**
The pipeline uses `ON CONFLICT ("tender_id") DO UPDATE` (upserts) continuously. If NHAI updates a tender, or if the user clicks "Re-analyze", the DB correctly updates the existing row without duplicating data or breaking foreign key relations.

---

## 7. Summary of Core Dashboard Logic

The interactive dashboard (the website) relies heavily on the FastAPI backend for data normalization and fluid interaction:
- When a user visits the dashboard, `server.py` queries Supabase and formats every tender into a unified frontend list view, determining automatically if a tender is active, closed, analyzed, or pending.
- When opening a specific tender, `_analysis_to_detail()` seamlessly translates the complex AI JSON output (like bank details, payment milestones, and technical eligibility criteria) into structured UI elements expected by the JavaScript frontend.
- By storing and providing direct URLs to the PDFs hosted in Supabase, the dashboard allows users to click an AI citation and instantly verify it against the actual source document. This ensures absolute trust in the LLM's outputs.
