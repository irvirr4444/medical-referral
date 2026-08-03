from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


MondayFieldName = Literal[
    "patient_name",
    "patient_date_of_birth",
    "patient_phone",
    "patient_email",
    "patient_address",
    "referring_agency",
    "current_home_health_or_hospice",
    "place_of_service",
    "wound_order_included",
    "wound_or_clinical_information",
    "insurance_information",
    "referral_or_order_date",
]


class MondayFieldEvidence(StrictModel):
    field_name: MondayFieldName
    page_numbers: list[int] = Field(
        default_factory=list,
        description="One-indexed PDF pages directly supporting the field.",
    )
    quote: str | None = Field(
        default=None,
        description="Short near-verbatim supporting text; null only when the value is visual-only.",
    )
    confidence: Literal["high", "medium", "low"] = "high"


class MondayInsuranceInformation(StrictModel):
    payer_name: str | None = None
    policy_number: str | None = None
    group_number: str | None = None
    insurance_type: Literal["Primary", "Secondary", "Tertiary", "Other"] | None = None


class MondayAgencyInformation(StrictModel):
    name: str | None = None
    contact_name: str | None = None
    phone: str | None = None
    email: str | None = None


class MondayPdfIntakeContract(StrictModel):
    patient_name: str | None = None
    patient_date_of_birth: str | None = Field(
        default=None,
        description="ISO YYYY-MM-DD when unambiguous; otherwise null.",
    )
    patient_phone: str | None = None
    patient_email: str | None = None
    patient_address: str | None = None
    referring_agency: MondayAgencyInformation = Field(
        default_factory=MondayAgencyInformation,
        description="The organization that sent or originated the referral, with its documented contact details.",
    )
    current_home_health_or_hospice: MondayAgencyInformation = Field(
        default_factory=MondayAgencyInformation,
        description="The patient's current HH/hospice company when explicitly documented; do not assume it is the referrer.",
    )
    place_of_service: str | None = None
    wound_order_included: bool | None = Field(
        default=None,
        description="True/false only when the PDF explicitly establishes whether a wound order is included.",
    )
    wound_or_clinical_information: str | None = Field(
        default=None,
        description="Concise referral-relevant wound/clinical summary, not a full historical diagnosis or medication list.",
    )
    insurance_information: list[MondayInsuranceInformation] = Field(default_factory=list)
    referral_or_order_date: str | None = Field(
        default=None,
        description="ISO YYYY-MM-DD for an explicit clinical referral/order/signature date; never use fax received time.",
    )
    sent_by: str | None = Field(
        default=None,
        description="Operational metadata supplied by the caller; never infer it from the PDF.",
    )
    evidence: list[MondayFieldEvidence] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
