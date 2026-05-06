"""
Section-specific AI prompts.
Every prompt enforces: cite exact page number + verbatim snippet, no hallucination.
"""

SYSTEM = """You are a senior infrastructure procurement analyst at Ernst & Young, India.
You extract information ONLY from the document text provided.
Rules you must never break:
1. Never invent, infer, or assume data not present in the text.
2. Every extracted value MUST have a page citation and a verbatim snippet (≤200 chars).
3. If a field is not found in the text, set it to "N/A" and leave its source list empty.
4. All numbers, dates, amounts (₹ figures, km, %, days) must be exact as written.
5. Use assertive language only — write what IS stated, not what "may" or "might" apply.
   Bad: "Consultant may be required to submit..."
   Good: "Consultant shall submit..."
6. Include specific numbers in every value field. Vague summaries are rejected.
7. Respond ONLY with valid JSON. No markdown, no explanation text outside the JSON."""


def key_dates_prompt(text: str) -> str:
    return f"""{SYSTEM}

Extract ALL dates and deadlines from the document text below.

Return JSON with this exact structure:
{{
  "pre_bid_meeting": "<date, time, venue or N/A>",
  "pre_bid_meeting_source": [{{"page": <int>, "snippet": "<verbatim quote>"}}],
  "last_date_clarification": "<date and time or N/A>",
  "last_date_clarification_source": [{{"page": <int>, "snippet": "<verbatim quote>"}}],
  "proposal_submission_deadline": "<date and time or N/A>",
  "proposal_submission_deadline_source": [{{"page": <int>, "snippet": "<verbatim quote>"}}],
  "technical_bid_opening": "<date and time or N/A>",
  "technical_bid_opening_source": [{{"page": <int>, "snippet": "<verbatim quote>"}}],
  "financial_bid_opening": "<date and time or N/A>",
  "financial_bid_opening_source": [{{"page": <int>, "snippet": "<verbatim quote>"}}],
  "bid_validity_period": "<e.g. 90 days from submission or N/A>",
  "bid_validity_period_source": [{{"page": <int>, "snippet": "<verbatim quote>"}}],
  "document_download_period": "<start date to end date or N/A>",
  "document_download_period_source": [{{"page": <int>, "snippet": "<verbatim quote>"}}]
}}

DOCUMENT TEXT:
{text}"""


def rfp_fees_prompt(text: str) -> str:
    return f"""{SYSTEM}

Extract all fee and payment details from the document text below.

Return JSON:
{{
  "rfp_fee_amount": "<exact amount in Rs or N/A>",
  "rfp_fee_source": [{{"page": <int>, "snippet": "<verbatim quote>"}}],
  "payment_mode": "<NEFT/RTGS/Online/DD or N/A>",
  "bank_details": {{
    "beneficiary_name": "<or N/A>",
    "account_number": "<or N/A>",
    "account_type": "<or N/A>",
    "bank_name": "<or N/A>",
    "branch": "<or N/A>",
    "ifsc_code": "<or N/A>"
  }},
  "bank_details_source": [{{"page": <int>, "snippet": "<verbatim quote>"}}],
  "emd_amount": "<exact amount or N/A>",
  "emd_source": [{{"page": <int>, "snippet": "<verbatim quote>"}}],
  "performance_security": "<exact % or amount or N/A>",
  "performance_security_source": [{{"page": <int>, "snippet": "<verbatim quote>"}}]
}}

DOCUMENT TEXT:
{text}"""


def eligibility_prompt(text: str) -> str:
    return f"""{SYSTEM}

Extract TECHNICAL and FINANCIAL eligibility criteria. Quote exact numbers — turnover figures,
experience years, project values, personnel counts. Do not generalize.

Return JSON:
{{
  "technical": {{
    "min_annual_turnover": "<exact Rs amount and financial years or N/A>",
    "min_annual_turnover_source": [{{"page": <int>, "snippet": "<verbatim quote>"}}],
    "similar_project_experience": "<exact description — lane type, km, value, years or N/A>",
    "similar_project_experience_source": [{{"page": <int>, "snippet": "<verbatim quote>"}}],
    "key_personnel_requirements": ["<role: qualification and years experience>"],
    "key_personnel_source": [{{"page": <int>, "snippet": "<verbatim quote>"}}],
    "jv_conditions": "<max partners, lead %, JV % or N/A>",
    "jv_conditions_source": [{{"page": <int>, "snippet": "<verbatim quote>"}}],
    "ongoing_assignment_cap": "<max concurrent NHAI assignments allowed or N/A>",
    "ongoing_assignment_cap_source": [{{"page": <int>, "snippet": "<verbatim quote>"}}],
    "other_conditions": ["<any other exact technical condition>"]
  }},
  "financial": {{
    "min_annual_turnover": "<exact Rs amount over how many years or N/A>",
    "min_annual_turnover_source": [{{"page": <int>, "snippet": "<verbatim quote>"}}],
    "net_worth_requirement": "<exact or N/A>",
    "net_worth_requirement_source": [{{"page": <int>, "snippet": "<verbatim quote>"}}],
    "financial_years_considered": "<e.g. best 3 of last 5 years or N/A>",
    "financial_years_considered_source": [{{"page": <int>, "snippet": "<verbatim quote>"}}],
    "other_conditions": ["<any other exact financial condition>"]
  }}
}}

DOCUMENT TEXT:
{text}"""


def evaluation_prompt(text: str) -> str:
    return f"""{SYSTEM}

Extract the complete evaluation and selection methodology. Include exact weightages, scores,
cut-off marks. State whether financial weightage exceeds technical.

Return JSON:
{{
  "selection_method": "<QCBS/QBS/LCS/FBS/CQS or N/A>",
  "selection_method_source": [{{"page": <int>, "snippet": "<verbatim quote>"}}],
  "technical_weightage": "<e.g. 80% or N/A>",
  "financial_weightage": "<e.g. 20% or N/A>",
  "weightage_source": [{{"page": <int>, "snippet": "<verbatim quote>"}}],
  "technical_min_qualifying_score": "<e.g. 75 out of 100 or N/A>",
  "financial_min_qualifying_score": "<or N/A>",
  "qualifying_score_source": [{{"page": <int>, "snippet": "<verbatim quote>"}}],
  "technical_evaluation_criteria": [
    {{"criterion": "<name>", "max_marks": "<number>", "sub_criteria": "<detail or N/A>"}}
  ],
  "pass_fail_criteria": ["<exact pass/fail condition as stated>"],
  "financial_higher_wins": <true if financial weightage > technical, else false>,
  "financial_higher_wins_source": [{{"page": <int>, "snippet": "<verbatim quote>"}}]
}}

DOCUMENT TEXT:
{text}"""


def scope_prompt(text: str) -> str:
    return f"""{SYSTEM}

Extract the full scope of work. Separate what the bidder must do (in-scope),
what the client provides (out-of-scope/client obligations), deliverables, milestones.
Be specific — include chainage, NH numbers, km, durations.

Return JSON:
{{
  "summary": "<2-3 sentence factual summary of what this assignment is>",
  "in_scope": [
    {{"description": "<exact task>", "source": [{{"page": <int>, "snippet": "<verbatim quote>"}}]}}
  ],
  "out_of_scope": [
    {{"description": "<what client/NHAI provides or does>", "source": [{{"page": <int>, "snippet": "<verbatim>"}}]}}
  ],
  "deliverables": [
    {{"description": "<deliverable name and description>", "source": [{{"page": <int>, "snippet": "<verbatim>"}}]}}
  ],
  "milestones": [
    {{"name": "<milestone>", "timeline": "<duration or date>", "deliverable": "<output>", "source": [{{"page": <int>, "snippet": "<verbatim>"}}]}}
  ],
  "client_obligations": ["<exact obligation of NHAI/client>"],
  "client_obligations_source": [{{"page": <int>, "snippet": "<verbatim quote>"}}],
  "contract_duration": "<exact period or N/A>",
  "contract_duration_source": [{{"page": <int>, "snippet": "<verbatim quote>"}}],
  "project_location": "<NH, section, km range, states or N/A>",
  "project_location_source": [{{"page": <int>, "snippet": "<verbatim quote>"}}]
}}

DOCUMENT TEXT:
{text}"""


def submission_prompt(text: str) -> str:
    return f"""{SYSTEM}

Extract all submission requirements: forms, formats, annexures, certifications.
List EVERY form and annexure mentioned by name. Note who must sign each form.

Return JSON:
{{
  "submission_mode": "<Online/Physical/Both or N/A>",
  "submission_mode_source": [{{"page": <int>, "snippet": "<verbatim quote>"}}],
  "portal": "<portal URL or name or N/A>",
  "portal_source": [{{"page": <int>, "snippet": "<verbatim quote>"}}],
  "required_forms": [
    {{
      "form_name": "<exact form ID e.g. Form T-1, Annex B-13>",
      "description": "<what this form is for>",
      "mandatory": true,
      "signing_authority": "<who signs — bidder/authorized signatory/notarized etc or N/A>",
      "source_page": <int>
    }}
  ],
  "certifications_required": ["<exact certification name>"],
  "certifications_source": [{{"page": <int>, "snippet": "<verbatim quote>"}}],
  "annexures_required": ["<exact annexure name and purpose>"],
  "annexures_source": [{{"page": <int>, "snippet": "<verbatim quote>"}}],
  "number_of_copies": "<e.g. 1 original + 2 copies or N/A>",
  "language": "<submission language or N/A>"
}}

DOCUMENT TEXT:
{text}"""


def contact_prompt(text: str) -> str:
    return f"""{SYSTEM}

Extract ALL contact persons and SPOC details. Include every name, designation,
address, phone, and email found. Return a list.

Return JSON — an array:
[
  {{
    "name": "<full name or N/A>",
    "designation": "<title/role or N/A>",
    "department": "<department/office or N/A>",
    "address": "<full address or N/A>",
    "phone": "<phone/fax or N/A>",
    "email": "<email or N/A>",
    "source": [{{"page": <int>, "snippet": "<verbatim quote>"}}]
  }}
]

DOCUMENT TEXT:
{text}"""


def payment_terms_prompt(text: str) -> str:
    return f"""{SYSTEM}

Extract all payment terms, milestone payments, and fee schedules.
Include exact percentages, amounts, and conditions.

Return JSON — an array:
[
  {{
    "milestone": "<milestone name>",
    "percentage": "<% of total fee or exact amount or N/A>",
    "condition": "<exact condition for payment as stated>",
    "source": [{{"page": <int>, "snippet": "<verbatim quote>"}}]
  }}
]

DOCUMENT TEXT:
{text}"""


def risk_prompt(text: str) -> str:
    return f"""{SYSTEM}

Extract risk, regulatory, legal, and penalty clauses.
Use exact figures for liquidated damages (rate, %, cap). No vague language — numbers and conditions only.
List the 5 most significant penalty clauses (skip minor procedural ones).

Return JSON:
{{
  "penalty_clauses": [
    {{
      "risk": "<exact penalty condition with specific % or amount>",
      "category": "<Legal/Financial/Operational/Regulatory>",
      "mitigation": "<mitigation if stated or N/A>",
      "source": [{{"page": <int>, "snippet": "<verbatim quote>"}}]
    }}
  ],
  "force_majeure": "<exact definition and consequences as stated or N/A>",
  "force_majeure_source": [{{"page": <int>, "snippet": "<verbatim quote>"}}],
  "termination_conditions": ["<exact termination clause>"],
  "termination_source": [{{"page": <int>, "snippet": "<verbatim quote>"}}],
  "dispute_resolution": "<arbitration clause — exact seats, rules, governing law or N/A>",
  "dispute_resolution_source": [{{"page": <int>, "snippet": "<verbatim quote>"}}],
  "integrity_pact": "<summary of integrity pact requirements or N/A>",
  "integrity_pact_source": [{{"page": <int>, "snippet": "<verbatim quote>"}}],
  "insurance_requirements": ["<exact insurance type and amount>"],
  "insurance_source": [{{"page": <int>, "snippet": "<verbatim quote>"}}],
  "liquidated_damages": "<exact rate/% and cap as stated or N/A>",
  "liquidated_damages_source": [{{"page": <int>, "snippet": "<verbatim quote>"}}]
}}

DOCUMENT TEXT:
{text}"""


def instructions_prompt(text: str) -> str:
    return f"""{SYSTEM}

Extract instructions to bidders, scope of work summary, and disqualification conditions.
Be precise — list exact disqualification triggers as stated.

Return JSON:
{{
  "overview": "<factual 2-3 sentence overview of bidding process>",
  "scope_of_work_summary": "<detailed factual scope — what bidder must deliver, specific activities>",
  "scope_of_work_source": [{{"page": <int>, "snippet": "<verbatim quote>"}}],
  "clarification_process": "<how and when to submit clarifications — exact deadline and method>",
  "clarification_source": [{{"page": <int>, "snippet": "<verbatim quote>"}}],
  "amendment_process": "<how amendments are issued or N/A>",
  "disqualification_conditions": ["<exact condition that leads to disqualification>"],
  "disqualification_source": [{{"page": <int>, "snippet": "<verbatim quote>"}}],
  "conflict_of_interest": "<exact conflict of interest rules or N/A>",
  "conflict_source": [{{"page": <int>, "snippet": "<verbatim quote>"}}]
}}

DOCUMENT TEXT:
{text}"""
