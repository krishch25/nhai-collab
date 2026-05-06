"""
Pydantic models for the complete tender analysis output.
Every field that carries extracted data has a companion `_source` field
with page citation(s) e.g. "Page 5", "Pages 6-7".
N/A string means present in schema but not found in document.
"""
from typing import Optional
from pydantic import BaseModel, Field


NA = "N/A"


class Citation(BaseModel):
    page: int
    snippet: str = Field(description="Exact verbatim quote from document (max 200 chars)")


class KeyDates(BaseModel):
    pre_bid_meeting: str = NA
    pre_bid_meeting_source: list[Citation] = []

    last_date_clarification: str = NA
    last_date_clarification_source: list[Citation] = []

    proposal_submission_deadline: str = NA
    proposal_submission_deadline_source: list[Citation] = []

    technical_bid_opening: str = NA
    technical_bid_opening_source: list[Citation] = []

    financial_bid_opening: str = NA
    financial_bid_opening_source: list[Citation] = []

    bid_validity_period: str = NA
    bid_validity_period_source: list[Citation] = []

    document_download_period: str = NA
    document_download_period_source: list[Citation] = []


class RFPFees(BaseModel):
    rfp_fee_amount: str = NA
    rfp_fee_source: list[Citation] = []

    payment_mode: str = NA          # NEFT/RTGS/Online
    bank_details: dict = {}         # beneficiary, account no, IFSC, bank
    bank_details_source: list[Citation] = []

    emd_amount: str = NA
    emd_source: list[Citation] = []

    performance_security: str = NA
    performance_security_source: list[Citation] = []


class TechnicalEligibility(BaseModel):
    min_annual_turnover: str = NA
    min_annual_turnover_source: list[Citation] = []

    similar_project_experience: str = NA
    similar_project_experience_source: list[Citation] = []

    key_personnel_requirements: list[str] = []
    key_personnel_source: list[Citation] = []

    jv_conditions: str = NA
    jv_conditions_source: list[Citation] = []

    ongoing_assignment_cap: str = NA
    ongoing_assignment_cap_source: list[Citation] = []

    other_conditions: list[str] = []


class FinancialEligibility(BaseModel):
    min_annual_turnover: str = NA
    min_annual_turnover_source: list[Citation] = []

    net_worth_requirement: str = NA
    net_worth_requirement_source: list[Citation] = []

    financial_years_considered: str = NA
    financial_years_considered_source: list[Citation] = []

    other_conditions: list[str] = []


class EligibilityCriteria(BaseModel):
    technical: TechnicalEligibility = TechnicalEligibility()
    financial: FinancialEligibility = FinancialEligibility()


class EvaluationCriteria(BaseModel):
    selection_method: str = NA       # QCBS, QBS, LCS, FBS, etc.
    selection_method_source: list[Citation] = []

    technical_weightage: str = NA    # e.g. "80%"
    financial_weightage: str = NA    # e.g. "20%"
    weightage_source: list[Citation] = []

    technical_min_qualifying_score: str = NA
    financial_min_qualifying_score: str = NA
    qualifying_score_source: list[Citation] = []

    technical_evaluation_criteria: list[dict] = []  # [{criterion, max_marks, source}]
    pass_fail_criteria: list[str] = []

    financial_higher_wins: bool = False   # True if financial > technical weightage
    financial_higher_wins_source: list[Citation] = []


class ScopeItem(BaseModel):
    description: str
    source: list[Citation] = []


class Milestone(BaseModel):
    name: str
    timeline: str = NA
    deliverable: str = NA
    source: list[Citation] = []


class ScopeOfRFP(BaseModel):
    summary: str = NA

    in_scope: list[ScopeItem] = []
    out_of_scope: list[ScopeItem] = []

    deliverables: list[ScopeItem] = []
    milestones: list[Milestone] = []

    client_obligations: list[str] = []   # what client/NHAI provides
    client_obligations_source: list[Citation] = []

    contract_duration: str = NA
    contract_duration_source: list[Citation] = []

    project_location: str = NA
    project_location_source: list[Citation] = []


class FormRequirement(BaseModel):
    form_name: str              # e.g. "Form T-1", "Annex B-13"
    description: str = NA
    mandatory: bool = True
    signing_authority: str = NA  # who must sign
    source_page: int = 0


class SubmissionMechanisms(BaseModel):
    submission_mode: str = NA           # Online / Physical / Both
    submission_mode_source: list[Citation] = []

    portal: str = NA                    # e.g. etenders.gov.in
    portal_source: list[Citation] = []

    required_forms: list[FormRequirement] = []
    certifications_required: list[str] = []
    certifications_source: list[Citation] = []

    annexures_required: list[str] = []
    annexures_source: list[Citation] = []

    number_of_copies: str = NA
    language: str = NA


class InstructionsToBidders(BaseModel):
    overview: str = NA

    scope_of_work_summary: str = NA     # detailed scope from TOR section
    scope_of_work_source: list[Citation] = []

    clarification_process: str = NA
    clarification_source: list[Citation] = []

    amendment_process: str = NA

    disqualification_conditions: list[str] = []
    disqualification_source: list[Citation] = []

    conflict_of_interest: str = NA
    conflict_source: list[Citation] = []


class ContactSPOC(BaseModel):
    name: str = NA
    designation: str = NA
    department: str = NA
    address: str = NA
    phone: str = NA
    email: str = NA
    source: list[Citation] = []


class PaymentTerm(BaseModel):
    milestone: str
    percentage: str = NA
    condition: str = NA
    source: list[Citation] = []


class RiskItem(BaseModel):
    risk: str
    category: str = NA   # Legal / Financial / Operational / Regulatory
    mitigation: str = NA
    source: list[Citation] = []


class RiskRegulatory(BaseModel):
    penalty_clauses: list[RiskItem] = []
    force_majeure: str = NA
    force_majeure_source: list[Citation] = []

    termination_conditions: list[str] = []
    termination_source: list[Citation] = []

    dispute_resolution: str = NA
    dispute_resolution_source: list[Citation] = []

    integrity_pact: str = NA
    integrity_pact_source: list[Citation] = []

    insurance_requirements: list[str] = []
    insurance_source: list[Citation] = []

    liquidated_damages: str = NA
    liquidated_damages_source: list[Citation] = []


class TenderDocument(BaseModel):
    description: str
    filename: str
    url: str
    local_path: Optional[str] = None
    filesize: str = NA
    extension: str
    supabase_path: Optional[str] = None
    is_form: bool = False
    download_error: Optional[str] = None


class TenderAnalysis(BaseModel):
    # Metadata
    tender_id: str
    tender_no: str
    title: str
    tender_type: str = "unknown"       # "2-stage" | "single-stage" | "unknown"
    analysis_version: str = "1.0"
    analyzed_at: str = ""
    source_documents: list[str] = []   # filenames analyzed
    confidence: str = "low"            # low | medium | high

    # All sections
    key_dates: KeyDates = KeyDates()
    rfp_fees: RFPFees = RFPFees()
    eligibility: EligibilityCriteria = EligibilityCriteria()
    evaluation: EvaluationCriteria = EvaluationCriteria()
    scope: ScopeOfRFP = ScopeOfRFP()
    submission: SubmissionMechanisms = SubmissionMechanisms()
    instructions: InstructionsToBidders = InstructionsToBidders()
    contacts: list[ContactSPOC] = []
    payment_terms: list[PaymentTerm] = []
    risk: RiskRegulatory = RiskRegulatory()

    # Documents & forms
    documents: list[TenderDocument] = []
