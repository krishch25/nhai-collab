# Progress 3 — Pipeline Debug, EY Theme, Full Backend Integration

**Date:** 2026-05-06  
**Session:** Complete pipeline audit + multi-doc fix + EY rebrand + backend-frontend integration  

---

## Bugs Found & Fixed

### 1. `server.py` — Duplicate Routes (CRITICAL)
**Bug:** Lines 576–584 re-declared `@app.get("/")`, `app.mount("/")`, and `if __name__` block — a second identical set. FastAPI would raise `ValueError` on startup when the static mount name `"frontend"` was registered twice.  
**Fix:** Removed the duplicate block entirely. Single route, single mount.

---

### 2. `analysis/engine.py` — Dead Code After `return` (BUG)
**Bug:** Lines 553–574 were unreachable — a complete duplicate `log.info(...)` + `return TenderAnalysis(...)` after the real return statement.  
**Fix:** Removed the dead block.

---

### 3. Multi-Document Analysis — Three Cascading Bugs (CRITICAL)

**Bug A — Page Number Collision:**  
`_merge_docs` appended secondary docs (NIT, corrigendum) with their original page numbers (1–8 for NIT). These collided with primary RFP pages 1–8. `text_for_pages([3])` would return both RFP page 3 AND NIT page 3, mixing content unpredictably.

**Bug B — Corrigendum Completely Ignored:**  
`get_pages_containing(..., min_page=6)` silently skips all pages with page_num < 6. The corrigendum only had 2 pages (page_num = 1, 2) — both skipped. The corrigendum was never sent to the AI.

**Bug C — NIT Pages 1–5 Filtered Out:**  
Same `min_page=6` filter cut NIT pages 1–5. These contained:
- Page 1: RFP title, consultant scope
- Page 2: Selection procedure (evaluation method)
- **Page 3: Bank account details, RFP fee (Rs 5,000), NEFT/RTGS** ← missed
- Page 4: Technical specs (NSV equipment)
- **Page 5: JV partner eligibility criteria** ← missed

**Fix:**

1. **Offset page numbering in `_merge_docs`**: Secondary docs now start at `primary.total_pages + 1`. No collisions. NIT pages become 252–259, accessible by section mapper.

2. **`_classify_docs`**: Classifies docs into `primary` (largest), `corrigenda` (name contains corrigendum/addendum/amendment, or ≤5 pages), `supplementary` (other secondary PDFs).

3. **`_build_section_text`**: New function builds combined section text:
   - Primary: section-mapped pages
   - Supplementary (≤20 pages): always included in full
   - Corrigenda: always included in full with `[SUPERSEDES]` label
   - Smart budget allocation: if total > max_chars, trim primary but preserve corrigenda + supplementary

4. **`_is_scanned`**: Detects image-only PDFs (zero extractable text). corrigendumI-I.pdf for tender 58050 is a scanned image — detected and skipped gracefully with a log warning instead of silently producing empty analysis.

5. **Combined key_dates pages**: Now merges section_map dates pages + keyword-found pages + early pages for maximum coverage.

**Before vs After for tender 58050:**

| Section | Before | After |
|---------|--------|-------|
| RFP fees | Missed NIT page 3 (Rs 5,000 fee, bank account) | ✓ NIT page 3 included |
| Eligibility | Missed NIT pages 1–5 (JV criteria, turnover) | ✓ All NIT pages included |
| Key dates | 1 page (p.25) only | ✓ 24 pages + full NIT |
| Corrigendum | Never sent to AI | ✓ Scanned — flagged in log, skipped cleanly |
| Text per section | 12,000 chars (truncated) | **40,000 chars** |

---

### 4. Context Limit & Batching

**`PDF_CHUNK_MAX_CHARS`**: Raised from 12,000 → 40,000 chars.  
GPT-5.1 has 128k context window. At 40k chars/section (~10k tokens), 10 parallel sections = 100k tokens total — well within budget.

**`_batch_section_ai_async`**: For sections > `PDF_BATCH_THRESHOLD` (70,000 chars), automatically:
1. Splits into overlapping 50,000-char chunks (500-char overlap for continuity)
2. Runs each chunk through AI in parallel
3. Merges results with a final AI call that reconciles partial responses

This handles very long RFPs where scope/risk sections exceed 70k chars.

---

## EY Theme Applied

### Colors
| Variable | Before | After (EY Brand) |
|----------|--------|-----------------|
| `--ink` | `#111111` | `#2E2E38` (EY charcoal) |
| `--paper-2` | `#f7f7f7` | `#F6F6FA` (EY light grey) |
| `--accent` | `oklch(0.50 0.05 195)` (teal) | `#FFE600` (EY Yellow) |
| `--accent-2` | `oklch(0.42 0.06 195)` | `#B8A400` (dark yellow for text) |
| `--accent-soft` | `oklch(0.94 0.02 195)` | `#FFFBE0` (yellow tint bg) |
| `--hi` / `--hi-soft` | amber | EY Yellow + rgba tint |
| Rule colors | `#e5e5e5` | `#E0E0E8` (EY border) |

### Fonts  
| Role | Before | After |
|------|--------|-------|
| Serif (headings) | `Newsreader` | `DM Serif Display` (closer to EY's editorial serif) |
| Sans (body) | `Inter` | `Inter` (unchanged — same as EY Interstate) |
| Mono | `JetBrains Mono` | `JetBrains Mono` (unchanged) |

### Interactive States
- Active nav tab: bottom border now `#FFE600` (EY Yellow) instead of black
- Section nav active: left border `#FFE600`, background `#FFFBE0`
- Primary button: `#FFE600` background + `#2E2E38` dark text (EY CTA style)
- Tweak panel: default accent swatch changed to EY Yellow (hue 100)
- `app.jsx`: `TWEAK_DEFAULTS.accentHue` changed from 195 (teal) → 100 (yellow)

---

## Backend-Frontend Integration

### New: "Fetch from NHAI" button (`list-view.jsx`)
- Button in page header: calls `POST /api/fetch`
- Pulls latest tenders from `nhai.gov.in`
- Auto-refreshes tender list on success
- Shows count of new tenders + analysis queue status

### Fixed: analyzeMsg padding  
Message bar now uses `padding: "10px 24px"` matching page-head (was `"0 0 12px"` with no horizontal padding — text bled to edge).

Message bar style changed to EY Yellow tint (`background: var(--accent-soft)`, `borderBottom: 1px solid var(--accent)`).

---

## Real Tender Test — Tender #58050

Pipeline verified end-to-end without AI (EYQ unavailable offline):

```
Primary: RFP_787.pdf — 251 pages
Supplementary: NIT_1359.pdf — 8 pages
Scanned (skipped): corrigendumI-I.pdf — image PDF, no text
Merged: 259 total pages, 0 collisions
Section map: 12 sections mapped
Key dates pages: 24 combined pages
Eligibility text: 39,967 chars (includes NIT JV criteria + turnover)
NIT bank account + RFP fee captured: ✓
```

---

## Files Modified

| File | Change |
|------|--------|
| `server.py` | Removed duplicate `root()`, `app.mount()`, `if __name__` block |
| `analysis/engine.py` | Fixed `_merge_docs`, added `_classify_docs`, `_build_section_text`, `_is_scanned`, `_is_corrigendum`, `_batch_section_ai_async`; raised char limits; removed dead code |
| `config.py` | `PDF_CHUNK_MAX_CHARS`: 12k→40k; added `PDF_BATCH_THRESHOLD=70k`, `PDF_BATCH_SIZE=50k` |
| `NHAI SCRAPPER/styles.css` | EY colors + `DM Serif Display` font |
| `NHAI SCRAPPER/app.jsx` | Default accent hue 195→100 (yellow), yellow swatch first |
| `NHAI SCRAPPER/list-view.jsx` | `fetchFromNHAI()` function + "Fetch from NHAI" button + fixed analyzeMsg padding |
| `progress/progress_3.md` | This file |
