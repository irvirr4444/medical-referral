from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


Confidence = Literal["high", "medium", "low"]


class FieldEvidence(StrictModel):
    field_path: str = Field(description="Dot path for the supported field, for example patient.date_of_birth")
    page_numbers: list[int] = Field(
        default_factory=list,
        description="One-indexed PDF pages that directly support the value",
    )
    quote: str | None = Field(
        default=None,
        description="Short, near-verbatim source text supporting the value; null when visual-only",
    )
    confidence: Confidence = "high"


class PatientCandidate(StrictModel):
    first_name: str | None = None
    middle_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    source_patient_id: str | None = Field(
        default=None,
        description="Patient/account/chart identifier when it is not explicitly labeled MRN",
    )
    source_patient_id_label: str | None = None
    mrn: str | None = Field(
        default=None,
        description="Only an identifier explicitly labeled MRN; never substitute an account or patient ID",
    )
    date_of_birth: str | None = None
    age: int | None = None
    gender: str | None = None
    address1: str | None = None
    address2: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    phone_number: str | None = None
    secondary_phone_number: str | None = None
    email: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None


class ReferringSourceCandidate(StrictModel):
    provider_name: str | None = None
    facility_name: str | None = None
    phone: str | None = None
    fax: str | None = None
    address: str | None = None
    referral_date: str | None = None


class AdmissionCandidate(StrictModel):
    admission_date: str | None = None
    facility_name: str | None = None
    facility_phone: str | None = None
    facility_fax: str | None = None
    home_health_company: str | None = None
    place_of_service: str | None = None
    medicare_admission: bool | None = None
    palliative_admission: bool | None = None
    hospice: bool | None = None


class DiagnosisCandidate(StrictModel):
    code: str | None = None
    description: str | None = None
    added_date: str | None = None
    is_primary: bool | None = None
    status: str | None = None


class MedicationCandidate(StrictModel):
    name: str | None = None
    strength: str | None = None
    dose_form: str | None = None
    directions: str | None = None
    status: str | None = None
    prescribed_date: str | None = None
    prescriber: str | None = None
    days_supply: int | None = None
    quantity: str | None = None
    refills: int | None = None


class AllergyCandidate(StrictModel):
    name: str | None = None
    reaction: str | None = None
    treatment: str | None = None
    status: str | None = None


class InsuranceCandidate(StrictModel):
    payer_name: str | None = None
    policy_number: str | None = None
    group_number: str | None = None
    group_name: str | None = None
    policy_holder_name: str | None = None
    insurance_type: Literal["Primary", "Secondary", "Tertiary", "Other"] | None = None
    effective_date: str | None = None
    expiration_date: str | None = None
    is_patient_policy_holder: bool | None = None
    subscriber_first_name: str | None = None
    subscriber_last_name: str | None = None
    subscriber_date_of_birth: str | None = None
    subscriber_relationship: str | None = None


class RequestedServiceCandidate(StrictModel):
    service: str | None = None
    frequency: str | None = None
    instructions: str | None = None


class IdentityReferralExtraction(StrictModel):
    document_type: str | None = None
    patient: PatientCandidate = Field(default_factory=PatientCandidate)
    referring_source: ReferringSourceCandidate = Field(default_factory=ReferringSourceCandidate)
    admission: AdmissionCandidate = Field(default_factory=AdmissionCandidate)
    requested_services: list[RequestedServiceCandidate] = Field(default_factory=list)
    other_clinical_notes: list[str] = Field(default_factory=list)
    evidence: list[FieldEvidence] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ClinicalExtraction(StrictModel):
    diagnoses_section_present: bool | None = None
    diagnoses: list[DiagnosisCandidate] = Field(default_factory=list)
    medications_section_present: bool | None = None
    medications: list[MedicationCandidate] = Field(default_factory=list)
    allergies_section_present: bool | None = None
    no_known_allergies_explicit: Literal[True] | None = Field(
        default=None,
        description="True only when the document explicitly states NKA/NKDA/no known allergies",
    )
    allergies: list[AllergyCandidate] = Field(default_factory=list)
    evidence: list[FieldEvidence] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class InsuranceExtraction(StrictModel):
    insurance_section_present: bool | None = None
    insurances: list[InsuranceCandidate] = Field(default_factory=list)
    evidence: list[FieldEvidence] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DrkPdfExtraction(StrictModel):
    document_type: str | None = None
    patient: PatientCandidate = Field(default_factory=PatientCandidate)
    referring_source: ReferringSourceCandidate = Field(default_factory=ReferringSourceCandidate)
    admission: AdmissionCandidate = Field(default_factory=AdmissionCandidate)
    diagnoses_section_present: bool | None = None
    diagnoses: list[DiagnosisCandidate] = Field(default_factory=list)
    medications_section_present: bool | None = None
    medications: list[MedicationCandidate] = Field(default_factory=list)
    allergies_section_present: bool | None = None
    no_known_allergies_explicit: Literal[True] | None = Field(
        default=None,
        description="True only when the document explicitly states NKA/NKDA/no known allergies",
    )
    allergies: list[AllergyCandidate] = Field(default_factory=list)
    insurance_section_present: bool | None = None
    insurances: list[InsuranceCandidate] = Field(default_factory=list)
    requested_services: list[RequestedServiceCandidate] = Field(default_factory=list)
    other_clinical_notes: list[str] = Field(default_factory=list)
    evidence: list[FieldEvidence] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
