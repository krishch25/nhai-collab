"""
Classify tender type (2-stage vs single-stage) and
map section keywords to their page locations in the document.
"""
from extraction.pdf import ExtractedDocument

# Section keyword maps — order matters (more specific first)
SECTION_KEYWORDS = {
    "key_dates": [
        "data sheet", "pre-proposal conference", "pre-bid meeting", "pre bid meeting",
        "proposal shall be valid", "bid validity", "clarification may be requested",
        "submission deadline", "bid submission end", "bid opening", "priced bid",
        "last date for submission", "last date of submission", "date of opening",
        "upto", "up to", "hrs.", "a.m.", "p.m.",
    ],
    "rfp_fees": [
        "rfp fee", "document fee", "non-refundable fee", "neft", "rtgs",
        "bank account", "ifsc", "payment of fee",
    ],
    "eligibility_technical": [
        "technical eligibility", "similar project", "key personnel",
        "team leader", "qualification criteria", "experience of",
        "annual turnover", "joint venture", "jv partner",
    ],
    "eligibility_financial": [
        "financial eligibility", "annual turnover", "net worth",
        "financial capability", "balance sheet", "audited",
    ],
    "evaluation_criteria": [
        "evaluation criteria", "selection criteria", "technical score",
        "financial score", "weightage", "marks", "scoring", "qcbs",
        "quality and cost", "pass/fail", "minimum qualifying",
    ],
    "scope_of_work": [
        "scope of work", "terms of reference", "tor ", "deliverable",
        "in-scope", "out of scope", "responsibilities of",
        "duties of", "services to be", "assignment",
    ],
    "submission_format": [
        "submission format", "format for submission", "annexure",
        "form-", "form t-", "form f-", "proforma", "checklist",
        "documents to be submitted", "enclosures",
    ],
    "instructions_to_bidders": [
        "instruction to bidder", "information to consultant",
        "general condition", "how to submit", "e-tendering",
        "online submission", "portal",
    ],
    "contact_spoc": [
        "contact", "single point of contact", "spoc",
        "nodal officer", "address for", "designated officer",
        "name and address",
    ],
    "payment_terms": [
        "payment term", "payment schedule", "invoice", "fee payment",
        "mobilization advance", "milestone payment",
    ],
    # Risk keywords that ONLY appear in contract conditions (not intro sections)
    "risk_regulatory": [
        "force majeure", "liquidated damage", "termination of contract",
        "dispute resolution", "arbitration clause", "indemnification",
        "insurance requirement", "integrity pact", "corrupt practice",
        "general conditions of contract", "suspension of services",
        "2.7", "2.9", "article", "gcc clause",
    ],
    "forms_annexures": [
        "annex", "annexure", "form-", "form t", "form f",
        "format ", "proforma", "declaration", "undertaking",
        "certificate", "power of attorney",
    ],
}

TWO_STAGE_SIGNALS = [
    "two stage", "2-stage", "two-stage", "stage 1", "stage 2",
    "request for qualification", "rfq", "shortlist", "shortlisted",
    "pre-qualification", "prequalification",
]

SINGLE_STAGE_SIGNALS = [
    "single stage", "one stage", "single envelope", "combined bid",
    "techno-commercial", "techno commercial",
]


def classify_tender_type(doc: ExtractedDocument) -> str:
    """Returns '2-stage', 'single-stage', or 'unknown'."""
    # Check first 30 pages — type is declared early
    sample_text = doc.text_for_pages(list(range(1, min(31, doc.total_pages + 1)))).lower()

    two_stage_score = sum(1 for s in TWO_STAGE_SIGNALS if s in sample_text)
    single_stage_score = sum(1 for s in SINGLE_STAGE_SIGNALS if s in sample_text)

    if two_stage_score > single_stage_score:
        return "2-stage"
    if single_stage_score > 0:
        return "single-stage"
    return "unknown"


def map_section_pages(doc: ExtractedDocument) -> dict[str, list[int]]:
    """Returns {section_name: [relevant_page_nums]} for each section."""
    result = {}
    for section, keywords in SECTION_KEYWORDS.items():
        pages = doc.get_pages_containing(keywords, window=1)
        result[section] = pages
    return result
