"""
Analysis engine: PDF text → section pages → AI → validated TenderAnalysis.

Handles all tender types:
- RFP (Consultancy): 2-stage, 100-300 pages, full sections
- NIT (Works/Services): single-stage, 5-50 pages, fewer sections
- NIQ (Quotation): minimal, 1-10 pages, basic extraction only
- Multi-document: merge text from NIT + RFP + Vol-I/II
"""
import asyncio
import json
import logging
import re
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
from pydantic import ValidationError

warnings.filterwarnings("ignore")  # suppress SSL warnings

from config import EYQ_URL, EYQ_KEY, EYQ_API_VERSION, AI_TIMEOUT, PDF_CHUNK_MAX_CHARS, PDF_BATCH_THRESHOLD, PDF_BATCH_SIZE
from extraction.pdf import ExtractedDocument, extract_document
from extraction.classifier import classify_tender_type, map_section_pages
from analysis.schema import (
    TenderAnalysis, KeyDates, RFPFees, EligibilityCriteria,
    TechnicalEligibility, FinancialEligibility, EvaluationCriteria,
    ScopeOfRFP, SubmissionMechanisms, InstructionsToBidders,
    ContactSPOC, PaymentTerm, RiskRegulatory, TenderDocument,
)
from analysis import prompts

log = logging.getLogger(__name__)


# ── AI call with retry + exponential backoff ────────────────────────────────

MAX_RETRIES = 4
BACKOFF_BASE = 15  # seconds — 15, 30, 60, 120

def _call_eyq(prompt: str) -> Optional[str]:
    for attempt in range(MAX_RETRIES):
        try:
            r = httpx.post(
                EYQ_URL,
                headers={"api-key": EYQ_KEY, "Content-Type": "application/json"},
                params={"api-version": EYQ_API_VERSION},
                json={"messages": [{"role": "user", "content": prompt}], "max_completion_tokens": 16000},
                timeout=AI_TIMEOUT,
                verify=False,
            )
            if r.status_code == 429:
                wait = BACKOFF_BASE * (2 ** attempt)
                log.warning("EYQ 429 rate limit — waiting %ds (attempt %d/%d)", wait, attempt+1, MAX_RETRIES)
                import time; time.sleep(wait)
                continue
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            log.error("EYQ call failed (attempt %d): %s", attempt+1, e)
            if attempt < MAX_RETRIES - 1:
                import time; time.sleep(BACKOFF_BASE * (2 ** attempt))
    return None


async def _call_eyq_async(client: httpx.AsyncClient, prompt: str) -> Optional[str]:
    """Async EYQ call with retry on 429."""
    for attempt in range(MAX_RETRIES):
        try:
            r = await client.post(
                EYQ_URL,
                headers={"api-key": EYQ_KEY, "Content-Type": "application/json"},
                params={"api-version": EYQ_API_VERSION},
                json={"messages": [{"role": "user", "content": prompt}], "max_completion_tokens": 16000},
            )
            if r.status_code == 429:
                wait = BACKOFF_BASE * (2 ** attempt)
                log.warning("EYQ async 429 — waiting %ds (attempt %d/%d)", wait, attempt+1, MAX_RETRIES)
                await asyncio.sleep(wait)
                continue
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            log.error("EYQ async call failed (attempt %d): %s", attempt+1, e)
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(BACKOFF_BASE * (2 ** attempt))
    return None


async def _run_sections_parallel(
    section_prompts: dict[str, str],
    section_prompt_fns: dict[str, any] = None,
) -> dict[str, Optional[str]]:
    """
    Run section prompts with concurrency limit to avoid 429.
    If section_prompt_fns provided, uses batched AI for oversized sections.
    """
    semaphore = asyncio.Semaphore(3)

    async def _limited(client, name, text, prompt_fn):
        async with semaphore:
            if prompt_fn and len(text) > PDF_BATCH_THRESHOLD:
                result = await _batch_section_ai_async(client, name, text, prompt_fn)
            else:
                result = await _call_eyq_async(client, prompt_fn(text) if prompt_fn else text)
            return name, result

    async with httpx.AsyncClient(timeout=AI_TIMEOUT, verify=False) as client:
        if section_prompt_fns:
            tasks = [
                _limited(client, name, text, section_prompt_fns.get(name))
                for name, text in section_prompts.items()
            ]
        else:
            tasks = [
                _limited(client, name, text, None)
                for name, text in section_prompts.items()
            ]
        pairs = await asyncio.gather(*tasks, return_exceptions=True)

    return {
        name: (r if not isinstance(r, Exception) else None)
        for name, r in pairs
        if isinstance(r, tuple)
    }


def _parse_json(raw: Optional[str]) -> Optional[dict | list]:
    if not raw:
        return None
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Try to repair truncated JSON
        try:
            # Find last complete object boundary
            for end in [raw.rfind("}"), raw.rfind("]")]:
                if end > 0:
                    candidate = raw[:end + 1]
                    return json.loads(candidate)
        except Exception:
            pass
        log.error("JSON parse failed. raw[:300]: %s", raw[:300])
        return None


def _chunk_text(text: str, max_chars: int = PDF_CHUNK_MAX_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    last_newline = truncated.rfind("\n")
    return truncated[:last_newline] if last_newline > 0 else truncated


# ── Document type detection ───────────────────────────────────────────────────

def _detect_doc_type(total_pages: int, filename: str, title: str) -> str:
    """Classify document complexity to adjust extraction strategy."""
    fname = filename.lower()
    title_lower = title.lower()
    if total_pages >= 80 or "rfp" in fname:
        return "rfp"
    if total_pages >= 20 or "nit" in fname or "vol" in fname:
        return "nit"
    return "niq"  # short quotation documents


# ── Section text builder ──────────────────────────────────────────────────────

def _section_text(
    doc: ExtractedDocument,
    section_map: dict[str, list[int]],
    section_key: str,
    fallback_pages: list[int] = None,
    max_chars: int = PDF_CHUNK_MAX_CHARS,
) -> str:
    pages = section_map.get(section_key, [])
    if not pages and fallback_pages:
        pages = fallback_pages
    elif not pages:
        pages = list(range(1, min(11, doc.total_pages + 1)))
    return _chunk_text(doc.text_for_pages(pages), max_chars)


def _risk_text(doc: ExtractedDocument, section_map: dict) -> str:
    """
    Risk/GCC section: find the start of 'General Conditions of Contract' or
    'Draft Form of Contract', then include all pages from there to end.
    Capped at 30 pages to fit in context.
    """
    gcc_start = None
    gcc_triggers = [
        "general conditions of contract",
        "draft form of contract",
        "section 7",
        "conditions of engagement",
    ]
    midpoint = doc.total_pages // 2

    for page in doc.pages:
        if page.page_num < midpoint:
            continue
        lower = page.text.lower()
        if any(t in lower for t in gcc_triggers):
            gcc_start = page.page_num
            break

    if gcc_start:
        risk_pages = list(range(gcc_start, min(gcc_start + 35, doc.total_pages + 1)))
    else:
        # Fallback: last 30 pages
        risk_pages = list(range(max(1, doc.total_pages - 30), doc.total_pages + 1))

    log.info("Risk pages (GCC section from p%s): %s", gcc_start, risk_pages[:10])
    return _chunk_text(doc.text_for_pages(risk_pages), max_chars=40000)


# ── Scanned PDF detection ─────────────────────────────────────────────────────

def _is_scanned(doc: ExtractedDocument) -> bool:
    """True if PDF produced no extractable text (image-only / scanned)."""
    return len(doc.pages) == 0


# ── Document role classification ─────────────────────────────────────────────

_CORRIGENDUM_NAMES = ["corrigendum", "addendum", "amendment", "erratum", "corr-", "addm"]
# Names that clearly identify the primary bidding document
_RFP_NAMES = ["rfp", "nit_", "nit-", "nit ", " nit", "request_for_proposal",
              "tender_doc", "bidding_document", "bid_document"]
# Names that indicate a supplementary contract/schedule (not the main RFP)
_CONTRACT_NAMES = ["epc_agreement", "epc agreement", "agreement_schedule",
                   "draft_contract", "schedule", "gcc", "special_condition"]


def _is_corrigendum(doc: ExtractedDocument) -> bool:
    name = doc.path.name.lower()
    return any(kw in name for kw in _CORRIGENDUM_NAMES) or doc.total_pages <= 5


def _is_rfp_doc(doc: ExtractedDocument) -> bool:
    """True if filename signals this is the primary RFP/NIT bidding document."""
    name = doc.path.name.lower()
    return any(kw in name for kw in _RFP_NAMES)


def _is_contract_doc(doc: ExtractedDocument) -> bool:
    """True if filename signals this is a contract/agreement (not the main RFP)."""
    name = doc.path.name.lower()
    return any(kw in name for kw in _CONTRACT_NAMES)


def _classify_docs(docs: list[ExtractedDocument]):
    """
    Return (primary, corrigenda, supplementary).
    Priority for primary:
      1. Explicitly named RFP/NIT docs
      2. Largest non-contract doc
      3. Largest overall doc (fallback)
    """
    readable = [d for d in docs if not _is_scanned(d)]
    if not readable:
        return None, [], []

    corrigenda = [d for d in readable if _is_corrigendum(d)]
    candidates = [d for d in readable if not _is_corrigendum(d)]
    if not candidates:
        return None, corrigenda, []

    # First choice: explicitly named RFP/NIT docs
    rfp_candidates = [d for d in candidates if _is_rfp_doc(d)]
    # Second choice: non-contract docs
    non_contract = [d for d in candidates if not _is_contract_doc(d)]

    if rfp_candidates:
        primary = max(rfp_candidates, key=lambda d: d.total_pages)
    elif non_contract:
        primary = max(non_contract, key=lambda d: d.total_pages)
    else:
        primary = max(candidates, key=lambda d: d.total_pages)

    supplementary = [d for d in candidates if d is not primary]
    return primary, corrigenda, supplementary


# ── Multi-document merge ──────────────────────────────────────────────────────

def _merge_docs(extracted_docs: list[ExtractedDocument]) -> ExtractedDocument:
    """
    Merge multiple PDFs into one working document.
    Secondary docs get OFFSET page numbers (no collisions).
    Small corrigenda are kept separate for special handling.
    """
    if len(extracted_docs) == 1:
        return extracted_docs[0]

    from extraction.pdf import PagedText

    # Sort: largest first (primary)
    sorted_docs = sorted(extracted_docs, key=lambda d: d.total_pages, reverse=True)
    primary = sorted_docs[0]

    all_pages = list(primary.pages)
    offset = primary.total_pages  # secondary pages start AFTER primary's last page

    for secondary in sorted_docs[1:]:
        for page in secondary.pages:
            labelled = PagedText(
                page_num=offset + page.page_num,  # unique, non-colliding page number
                text=f"[FROM: {secondary.path.name}, original p.{page.page_num}]\n{page.text}"
            )
            all_pages.append(labelled)
        offset += secondary.total_pages

    from extraction.pdf import ExtractedDocument as ED
    merged = ED(path=primary.path, pages=all_pages)
    merged.total_pages = offset  # real total across all docs
    return merged


# ── Combined section text builder ─────────────────────────────────────────────

def _build_section_text(
    primary: ExtractedDocument,
    section_pages: list[int],
    corrigenda: list[ExtractedDocument],
    supplementary: list[ExtractedDocument],
    max_chars: int = PDF_CHUNK_MAX_CHARS,
    include_all_supplementary: bool = False,
) -> str:
    """
    Build section text from primary + corrigenda + supplementary docs.
    Corrigenda are ALWAYS fully included (they supersede primary).
    Supplementary docs contribute their full text when include_all_supplementary=True
    (used for small secondary docs like NITs that are ≤20 pages).
    """
    parts = []

    # Primary section pages
    if section_pages:
        primary_text = primary.text_for_pages(section_pages)
    else:
        # Fallback: first 10 pages
        primary_text = primary.text_for_pages(list(range(1, min(11, primary.total_pages + 1))))

    parts.append(primary_text)

    # Supplementary docs (NIT etc.) — include full text for small docs
    for sup in supplementary:
        if include_all_supplementary or sup.total_pages <= 20:
            sup_text = sup.full_text()
            parts.append(f"\n\n[SUPPLEMENTARY DOCUMENT: {sup.path.name}]\n{sup_text}")

    # Corrigenda — ALWAYS include fully (small docs, supersede primary)
    for corr in corrigenda:
        corr_text = corr.full_text()
        parts.append(f"\n\n[CORRIGENDUM/AMENDMENT: {corr.path.name} — SUPERSEDES PRIMARY DOCUMENT WHERE APPLICABLE]\n{corr_text}")

    combined = "".join(parts)

    if len(combined) <= max_chars:
        return combined

    # Over limit: keep corrigenda + supplementary in full, trim primary
    reserved = sum(
        len(f"\n\n[SUPPLEMENTARY DOCUMENT: {s.path.name}]\n{s.full_text()}")
        for s in supplementary if s.total_pages <= 20
    ) + sum(
        len(f"\n\n[CORRIGENDUM/AMENDMENT: {c.path.name} — SUPERSEDES PRIMARY DOCUMENT WHERE APPLICABLE]\n{c.full_text()}")
        for c in corrigenda
    )
    primary_budget = max_chars - reserved
    if primary_budget > 2000:
        primary_trimmed = _chunk_text(primary_text, primary_budget)
    else:
        # Very tight: just keep corrigenda + first 2000 chars of primary
        primary_trimmed = primary_text[:2000]

    trimmed_parts = [primary_trimmed]
    for sup in supplementary:
        if include_all_supplementary or sup.total_pages <= 20:
            trimmed_parts.append(f"\n\n[SUPPLEMENTARY DOCUMENT: {sup.path.name}]\n{sup.full_text()}")
    for corr in corrigenda:
        trimmed_parts.append(f"\n\n[CORRIGENDUM/AMENDMENT: {corr.path.name} — SUPERSEDES PRIMARY DOCUMENT WHERE APPLICABLE]\n{corr.full_text()}")

    return "".join(trimmed_parts)


# ── Batched AI call for oversized sections ────────────────────────────────────

async def _batch_section_ai_async(
    client: httpx.AsyncClient,
    section_name: str,
    full_text: str,
    prompt_fn,
) -> Optional[str]:
    """
    When section text exceeds PDF_BATCH_THRESHOLD, split into overlapping batches,
    run each through AI, then merge the results into a final authoritative response.
    """
    if len(full_text) <= PDF_BATCH_THRESHOLD:
        return await _call_eyq_async(client, prompt_fn(full_text))

    log.info("[%s] Section too large (%d chars), batching into chunks", section_name, len(full_text))

    # Build overlapping chunks (500-char overlap for context continuity)
    chunks = []
    start = 0
    overlap = 500
    while start < len(full_text):
        end = min(start + PDF_BATCH_SIZE, len(full_text))
        chunks.append(full_text[start:end])
        if end >= len(full_text):
            break
        start = end - overlap

    log.info("[%s] Split into %d batches", section_name, len(chunks))

    # Run all batches
    tasks = [_call_eyq_async(client, prompt_fn(chunk)) for chunk in chunks]
    batch_results = await asyncio.gather(*tasks, return_exceptions=True)
    valid_results = [r for r in batch_results if isinstance(r, str) and r]

    if not valid_results:
        return None
    if len(valid_results) == 1:
        return valid_results[0]

    # Merge: ask AI to combine partial results into final answer
    merge_prompt = (
        f"You ran {len(valid_results)} parallel analysis passes on different sections of the same document. "
        f"Merge these JSON results into ONE final authoritative JSON. "
        f"If fields appear in multiple results, prefer the more specific/complete value. "
        f"Keep all unique entries. Do NOT summarize — return valid JSON only.\n\n"
        + "\n\n---RESULT---\n".join(valid_results)
    )
    merged = await _call_eyq_async(client, merge_prompt)
    return merged if merged else valid_results[0]


# ── API date pre-seeding ──────────────────────────────────────────────────────

def _extract_api_dates(api_detail: dict) -> dict:
    """Pull guaranteed-accurate dates from the API response."""
    if not api_detail:
        return {}
    imp = (api_detail.get("important_dates") or [{}])[0]
    result = {}
    if imp.get("Bid Submission End Date"):
        result["proposal_submission_deadline"] = imp["Bid Submission End Date"]
    if imp.get("Bid Opening Date Time"):
        result["technical_bid_opening"] = imp["Bid Opening Date Time"]
    if imp.get("Priced Bid Opening Date"):
        result["financial_bid_opening"] = imp["Priced Bid Opening Date"]
    if imp.get("Pre Bid Meeting Date"):
        result["pre_bid_meeting"] = imp["Pre Bid Meeting Date"]
    start = imp.get("Tender Document Sales Start Date", "")
    end = imp.get("Tender Document Sales End Date", "")
    if start or end:
        result["document_download_period"] = f"{start} to {end}".strip(" to ")
    return result


# ── Section extractor ─────────────────────────────────────────────────────────

def _run_section(prompt_fn, text: str, model_cls, fallback):
    raw = _call_eyq(prompt_fn(text))
    data = _parse_json(raw)
    if data is None:
        return fallback
    try:
        if isinstance(data, list):
            return data
        return model_cls(**data)
    except (ValidationError, TypeError):
        try:
            return model_cls.model_validate(data)
        except Exception:
            return fallback


# ── Main orchestrator ─────────────────────────────────────────────────────────

def analyze_tender(
    tender_id: str,
    tender_no: str,
    title: str,
    downloaded_docs: list[dict],
    api_detail: dict = None,
) -> TenderAnalysis:
    """
    Complete pipeline for ANY tender type.
    Handles: 0 docs, 1 doc, many docs, short NIQ, long RFP.
    """
    log.info("═══ Analyzing tender %s — %s ═══", tender_id, tender_no)

    # ── Build document objects ────────────────────────────────────────────────
    doc_objects: list[TenderDocument] = []
    extracted_docs: list[ExtractedDocument] = []

    for d in downloaded_docs:
        td = TenderDocument(
            description=d.get("description", ""),
            filename=d.get("filename", ""),
            url=d.get("url", ""),
            local_path=d.get("local_path"),
            filesize=d.get("filesize", "N/A"),
            extension=d.get("extension", ""),
            download_error=d.get("error"),
        )
        doc_objects.append(td)

        if d.get("local_path") and not d.get("error"):
            path = Path(d["local_path"])
            if path.suffix.lower() == ".pdf":
                try:
                    extracted = extract_document(path)
                    if extracted:
                        log.info("  PDF: %s — %d pages", path.name, extracted.total_pages)
                        extracted_docs.append(extracted)
                except Exception as e:
                    log.error("  PDF extract failed %s: %s", path.name, e)

    # ── API pre-seeding ───────────────────────────────────────────────────────
    api_dates = _extract_api_dates(api_detail)
    api_basic = {}
    if api_detail:
        basic = (api_detail.get("basic_information") or [{}])[0]
        api_basic = {
            "emd_amount": basic.get("EMD Value", ""),
            "rfp_fee_amount": basic.get("Application Fee", ""),
            "tender_type_raw": basic.get("Tender Type", ""),
            "procurement_cat": basic.get("Procurement Category", ""),
        }

    # Log scanned (image-only) PDFs — cannot extract text
    for d in extracted_docs:
        if _is_scanned(d):
            log.warning("  SCANNED (no text): %s — skipped for AI extraction", d.path.name)

    # ── Classify docs into roles ──────────────────────────────────────────────
    primary, corrigenda, supplementary = _classify_docs(extracted_docs)

    if primary is None:
        log.warning("No readable PDFs — building analysis from API data only")
        key_dates = KeyDates(**{k: v for k, v in api_dates.items() if v})
        rfp_fees = RFPFees(
            emd_amount=api_basic.get("emd_amount") or "N/A",
            rfp_fee_amount=api_basic.get("rfp_fee_amount") or "N/A",
        )
        return TenderAnalysis(
            tender_id=tender_id, tender_no=tender_no, title=title,
            tender_type="unknown", confidence="low",
            analyzed_at=datetime.now(timezone.utc).isoformat(),
            key_dates=key_dates, rfp_fees=rfp_fees,
            documents=doc_objects,
        )

    log.info("Primary doc: %s (%d pages)", primary.path.name, primary.total_pages)
    log.info("Corrigenda: %s", [d.path.name for d in corrigenda])
    log.info("Supplementary: %s", [d.path.name for d in supplementary])

    doc_type = _detect_doc_type(primary.total_pages, primary.path.name, title)
    tender_type = classify_tender_type(primary)
    log.info("Doc type: %s | Tender type: %s | Primary pages: %d",
             doc_type, tender_type, primary.total_pages)

    # ── Merge primary + supplementary for section mapping ────────────────────
    # (corrigenda stay separate — always appended via _build_section_text)
    all_for_merge = [primary] + supplementary
    working_doc = _merge_docs(all_for_merge)

    section_map = map_section_pages(working_doc)
    log.info("Section map: %s", {k: v[:3] for k, v in section_map.items() if v})

    # Helper: build text for a section with corrigenda always appended
    def sec(section_key, fallback_pages=None, max_chars=PDF_CHUNK_MAX_CHARS, include_all_sup=True):
        pages = section_map.get(section_key, [])
        if not pages and fallback_pages:
            pages = fallback_pages
        elif not pages:
            pages = list(range(1, min(11, primary.total_pages + 1)))
        return _build_section_text(
            primary=primary,
            section_pages=sorted(set(pages)),
            corrigenda=corrigenda,
            supplementary=supplementary,
            max_chars=max_chars,
            include_all_supplementary=include_all_sup,
        )

    # ── KEY DATES ─────────────────────────────────────────────────────────────
    log.info("→ Building section texts")
    data_sheet_pages = working_doc.get_pages_containing(
        ["pre-proposal conference", "proposal shall be valid", "last date of submission",
         "last date for submission"],
        window=0, min_page=4,
    )
    early_date_pages = working_doc.get_pages_containing(
        ["bid submission end", "bid opening", "upto", "download"],
        window=0, min_page=2,
    )
    # Combine: keyword-found pages + section_map dates pages + fallback
    kd_map_pages = section_map.get("key_dates", [])
    priority_pages = sorted(set(data_sheet_pages + early_date_pages + kd_map_pages))[:25]
    if not priority_pages:
        priority_pages = list(range(1, min(16, primary.total_pages + 1)))
    kd_text = _build_section_text(
        primary=primary,
        section_pages=priority_pages,
        corrigenda=corrigenda,
        supplementary=supplementary,
        max_chars=PDF_CHUNK_MAX_CHARS,
        include_all_supplementary=True,
    )
    log.info("Key date pages from working_doc: %s", priority_pages[:10])

    # ── ELIGIBILITY ───────────────────────────────────────────────────────────
    elig_base = sorted(set(
        section_map.get("eligibility_technical", []) +
        section_map.get("eligibility_financial", [])
    ))
    elig_dense = [p.page_num for p in working_doc.pages if
                  sum(1 for kw in ["turnover", "experience", "personnel", "joint venture",
                                   "eligible", "qualification", "net worth"]
                      if kw in p.text.lower()) >= 3]
    elig_pages = sorted(set(elig_base + elig_dense))[:25]
    elig_text = _build_section_text(primary, elig_pages or list(range(1, 15)),
                                     corrigenda, supplementary,
                                     max_chars=PDF_CHUNK_MAX_CHARS, include_all_supplementary=True)

    # ── EVALUATION ────────────────────────────────────────────────────────────
    eval_dense = [p.page_num for p in working_doc.pages if
                  sum(1 for kw in ["marks", "weightage", "score", "qcbs",
                                   "technical proposal", "financial proposal", "selection"]
                      if kw in p.text.lower()) >= 3]
    eval_pages = sorted(set(section_map.get("evaluation_criteria", []) + eval_dense))[:20]
    eval_text = _build_section_text(primary, eval_pages or list(range(1, 15)),
                                     corrigenda, supplementary,
                                     max_chars=PDF_CHUNK_MAX_CHARS, include_all_supplementary=True)

    # ── SCOPE ─────────────────────────────────────────────────────────────────
    scope_dense = [p.page_num for p in working_doc.pages if
                   sum(1 for kw in ["scope", "deliverable", "supervision", "inspection",
                                    "report", "survey", "monitoring", "terms of reference"]
                       if kw in p.text.lower()) >= 4]
    scope_pages = sorted(set(section_map.get("scope_of_work", []) +
                              list(range(1, 6)) + scope_dense[:15]))
    scope_text = _build_section_text(primary, scope_pages,
                                      corrigenda, supplementary,
                                      max_chars=PDF_CHUNK_MAX_CHARS, include_all_supplementary=True)

    # ── SUBMISSION ────────────────────────────────────────────────────────────
    sub_dense = [p.page_num for p in working_doc.pages if
                 sum(1 for kw in ["form-", "annexure", "format", "checklist", "certif",
                                  "power of attorney", "undertaking", "proforma"]
                     if kw in p.text.lower()) >= 3]
    sub_pages = sorted(set(section_map.get("submission_format", []) + sub_dense[:20]))
    sub_text = _build_section_text(primary, sub_pages or list(range(1, 15)),
                                    corrigenda, supplementary,
                                    max_chars=PDF_CHUNK_MAX_CHARS, include_all_supplementary=True)

    # ── INSTRUCTIONS ──────────────────────────────────────────────────────────
    inst_pages = sorted(set(section_map.get("instructions_to_bidders", []) +
                            list(range(1, 10))))
    inst_text = _build_section_text(primary, inst_pages,
                                     corrigenda, supplementary,
                                     max_chars=PDF_CHUNK_MAX_CHARS, include_all_supplementary=True)

    # ── CONTACT ───────────────────────────────────────────────────────────────
    contact_text = sec("contact_spoc", fallback_pages=list(range(1, 10)))

    # ── PAYMENT TERMS ─────────────────────────────────────────────────────────
    payment_text = sec("payment_terms", fallback_pages=list(range(1, 15)))

    # ── RFP FEES ──────────────────────────────────────────────────────────────
    fees_text = sec("rfp_fees", fallback_pages=list(range(1, 12)))

    # ── RISK / GCC ────────────────────────────────────────────────────────────
    risk_text_val = _risk_text(working_doc, section_map)
    # Append corrigenda to risk text (corrigenda may amend LD clauses)
    for corr in corrigenda:
        risk_text_val += f"\n\n[CORRIGENDUM: {corr.path.name}]\n{corr.full_text()}"

    # ── Run ALL section prompts in PARALLEL (with auto-batching for large sections) ──
    log.info("→ Running all sections in parallel (with auto-batching if needed)...")
    section_texts = {
        "key_dates":    kd_text,
        "rfp_fees":     fees_text,
        "eligibility":  elig_text,
        "evaluation":   eval_text,
        "scope":        scope_text,
        "submission":   sub_text,
        "instructions": inst_text,
        "contacts":     contact_text,
        "payment":      payment_text,
        "risk":         risk_text_val,
    }
    section_prompt_fns = {
        "key_dates":    prompts.key_dates_prompt,
        "rfp_fees":     prompts.rfp_fees_prompt,
        "eligibility":  prompts.eligibility_prompt,
        "evaluation":   prompts.evaluation_prompt,
        "scope":        prompts.scope_prompt,
        "submission":   prompts.submission_prompt,
        "instructions": prompts.instructions_prompt,
        "contacts":     prompts.contact_prompt,
        "payment":      prompts.payment_terms_prompt,
        "risk":         prompts.risk_prompt,
    }
    for name, text in section_texts.items():
        log.info("  [%s] %d chars%s", name, len(text),
                 " → BATCHING" if len(text) > PDF_BATCH_THRESHOLD else "")

    raw_responses = asyncio.run(_run_sections_parallel(section_texts, section_prompt_fns))
    log.info("→ All parallel calls done")

    # ── KEY DATES ─────────────────────────────────────────────────────────────
    kd_data = _parse_json(raw_responses.get("key_dates")) or {}
    for field, val in api_dates.items():
        if val and (not kd_data.get(field) or kd_data.get(field) == "N/A"):
            kd_data[field] = val
    try:
        key_dates = KeyDates(**kd_data)
    except Exception:
        key_dates = KeyDates(**{k: v for k, v in api_dates.items() if v})

    # ── RFP FEES ──────────────────────────────────────────────────────────────
    fees_data = _parse_json(raw_responses.get("rfp_fees")) or {}
    if api_basic.get("emd_amount") and (not fees_data.get("emd_amount") or fees_data.get("emd_amount") == "N/A"):
        fees_data["emd_amount"] = api_basic["emd_amount"]
    if api_basic.get("rfp_fee_amount") and (not fees_data.get("rfp_fee_amount") or fees_data.get("rfp_fee_amount") == "N/A"):
        fees_data["rfp_fee_amount"] = api_basic["rfp_fee_amount"]
    try:
        rfp_fees = RFPFees(**fees_data)
    except Exception:
        rfp_fees = RFPFees()

    # ── ELIGIBILITY ───────────────────────────────────────────────────────────
    elig_data = _parse_json(raw_responses.get("eligibility")) or {}
    try:
        eligibility = EligibilityCriteria(
            technical=TechnicalEligibility(**(elig_data.get("technical") or {})),
            financial=FinancialEligibility(**(elig_data.get("financial") or {})),
        )
    except Exception:
        eligibility = EligibilityCriteria()

    # ── EVALUATION ────────────────────────────────────────────────────────────
    eval_data = _parse_json(raw_responses.get("evaluation")) or {}
    try:
        evaluation = EvaluationCriteria(**eval_data)
    except Exception:
        evaluation = EvaluationCriteria()

    # ── SCOPE ─────────────────────────────────────────────────────────────────
    scope_data = _parse_json(raw_responses.get("scope")) or {}
    try:
        scope = ScopeOfRFP(**scope_data)
    except Exception:
        scope = ScopeOfRFP()

    # ── SUBMISSION ────────────────────────────────────────────────────────────
    sub_data = _parse_json(raw_responses.get("submission")) or {}
    try:
        submission = SubmissionMechanisms(**sub_data)
    except Exception:
        submission = SubmissionMechanisms()

    # ── INSTRUCTIONS ──────────────────────────────────────────────────────────
    inst_data = _parse_json(raw_responses.get("instructions")) or {}
    try:
        instructions = InstructionsToBidders(**inst_data)
    except Exception:
        instructions = InstructionsToBidders()

    # ── CONTACTS ──────────────────────────────────────────────────────────────
    contacts_data = _parse_json(raw_responses.get("contacts")) or []
    contacts = []
    if isinstance(contacts_data, list):
        for c in contacts_data:
            try:
                contacts.append(ContactSPOC(**c))
            except Exception:
                pass

    # ── PAYMENT TERMS ─────────────────────────────────────────────────────────
    pay_data = _parse_json(raw_responses.get("payment")) or []
    payment_terms = []
    if isinstance(pay_data, list):
        for p in pay_data:
            try:
                payment_terms.append(PaymentTerm(**p))
            except Exception:
                pass

    # ── RISK ──────────────────────────────────────────────────────────────────
    risk_data = _parse_json(raw_responses.get("risk")) or {}
    try:
        risk = RiskRegulatory(**risk_data)
    except Exception:
        risk = RiskRegulatory()

    # ── Confidence ────────────────────────────────────────────────────────────
    filled = sum([
        key_dates.proposal_submission_deadline not in ("N/A", ""),
        eligibility.technical.min_annual_turnover not in ("N/A", ""),
        evaluation.selection_method not in ("N/A", ""),
        scope.summary not in ("N/A", ""),
        bool(contacts),
        bool(payment_terms),
        risk.force_majeure not in ("N/A", ""),
    ])
    confidence = "high" if filled >= 5 else "medium" if filled >= 3 else "low"

    log.info("═══ Analysis done — confidence=%s doc_type=%s ═══", confidence, doc_type)

    return TenderAnalysis(
        tender_id=tender_id,
        tender_no=tender_no,
        title=title,
        tender_type=tender_type,
        analyzed_at=datetime.now(timezone.utc).isoformat(),
        source_documents=[d.path.name for d in [primary] + corrigenda + supplementary],
        confidence=confidence,
        key_dates=key_dates,
        rfp_fees=rfp_fees,
        eligibility=eligibility,
        evaluation=evaluation,
        scope=scope,
        submission=submission,
        instructions=instructions,
        contacts=contacts,
        payment_terms=payment_terms,
        risk=risk,
        documents=doc_objects,
    )
