from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


DuplicateDecisionStatus = Literal[
    "clear_to_create",
    "duplicate_found",
    "manual_review_required",
    "not_checked",
]


class DrkDemographicsDraft(StrictModel):
    first_name: str | None = None
    middle_name: str | None = None
    last_name: str | None = None
    suffix: str | None = None
    ssn: str | None = None
    date_of_birth: str | None = None
    gender: str | None = None
    preferred_language: str | None = None


class DrkAddressDraft(StrictModel):
    address_line_1: str | None = None
    address_line_2: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    country: str | None = None


class DrkContactDraft(StrictModel):
    primary_phone: str | None = None
    secondary_phone: str | None = None
    email: str | None = None
    fax: str | None = None


class DrkEmergencyContactDraft(StrictModel):
    relationship: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    patient_guardian: bool | None = None
    address_line_1: str | None = None
    address_line_2: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None


class DrkAdmissionDraft(StrictModel):
    admission_date: str | None = None
    place_of_service_query: str | None = None
    facility_query: str | None = None
    home_health_query: str | None = None
    provider_query: str | None = None
    territory_query: str | None = None
    medicare_admission: bool | None = None
    palliative_care: bool | None = None
    hospice: bool | None = None


class DrkReferralDraft(StrictModel):
    referral_source_query: str | None = None
    referral_date: str | None = None
    clinical_referring_provider: str | None = None
    clinical_referring_facility: str | None = None


class DrkSubscriberDraft(StrictModel):
    first_name: str | None = None
    last_name: str | None = None
    date_of_birth: str | None = None
    relationship_to_patient: str | None = None


class DrkInsuranceDraft(StrictModel):
    payer_query: str | None = None
    insurance_type: str | None = None
    policy_number: str | None = None
    group_number: str | None = None
    group_name: str | None = None
    verified_with: str | None = None
    effective_date: str | None = None
    termination_date: str | None = None
    copay: str | None = None
    deductible_amount: str | None = None
    percent_coverage: str | None = None
    deductible_met: str | None = None
    is_patient_policy_holder: bool | None = None
    subscriber: DrkSubscriberDraft | None = None


class DrkCreatePayloadDraft(StrictModel):
    demographics: DrkDemographicsDraft = Field(default_factory=DrkDemographicsDraft)
    primary_address: DrkAddressDraft = Field(default_factory=DrkAddressDraft)
    secondary_address: DrkAddressDraft = Field(default_factory=DrkAddressDraft)
    contact: DrkContactDraft = Field(default_factory=DrkContactDraft)
    emergency_contact: DrkEmergencyContactDraft = Field(default_factory=DrkEmergencyContactDraft)
    admission: DrkAdmissionDraft = Field(default_factory=DrkAdmissionDraft)
    referral: DrkReferralDraft = Field(default_factory=DrkReferralDraft)
    insurances: list[DrkInsuranceDraft] = Field(default_factory=list)


class DrkCreateDraftEnvelope(StrictModel):
    payload: DrkCreatePayloadDraft
    ready_for_fill: bool
    blockers: list[str] = Field(default_factory=list)
    unresolved_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DrkFieldComparison(StrictModel):
    field_name: str
    incoming_value: str | None = None
    candidate_value: str | None = None
    outcome: Literal["match", "mismatch", "missing_incoming", "missing_candidate", "inconclusive"]


class DrkDuplicateCandidateAssessment(StrictModel):
    patient_id: str
    display_name: str | None = None
    classification: Literal["duplicate", "different_person", "suspicious", "inconclusive"]
    reason: str
    comparisons: list[DrkFieldComparison] = Field(default_factory=list)
    demographics: dict[str, object] | None = None


class DrkDuplicateCheckDecision(StrictModel):
    status: DuplicateDecisionStatus
    searched_name: str | None = None
    result_count: int | None = None
    row_count: int | None = None
    summary_text: str | None = None
    candidate_patient_ids: list[str] = Field(default_factory=list)
    assessments: list[DrkDuplicateCandidateAssessment] = Field(default_factory=list)
    reason: str
    clear_to_create: bool = False
    checked_at_utc: str | None = None
    error: str | None = None
