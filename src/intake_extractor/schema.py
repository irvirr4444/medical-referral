"""
Pydantic schema for normalized referral/intake data.

Design notes (see PROJECT_BRIEF.md field inventory for the full rationale):
- Fields are optional almost everywhere on purpose. Source documents vary
  widely in what they contain; a missing field is expected, not an error.
- icd10_codes is a flat list regardless of whether the source presented a
  single code, a problem list, or an ICD-10/ICD-9 table — normalization of
  that shape happens in the LLM prompt, not in this schema.
- requested_services covers both explicit referral checkboxes (e.g. "Wound
  Care") and implied orders/prescriptions (e.g. a DME Rx line item) — use
  `instructions` for Rx-style quantity/schedule detail that doesn't fit
  `frequency`.
- Sporadic fields seen in only 1-2 source layouts (allergies, guarantor,
  employer, emergency contact, homebound justification, etc.) are
  deliberately NOT modeled as structured fields yet — they fold into
  `notes`. Promote one to a structured field only once a real downstream
  consumer needs it; a schema that's mostly-null across every document type
  is a maintenance cost, not a feature.
"""

from pydantic import BaseModel, Field


class RequestedService(BaseModel):
    service: str | None = Field(
        None,
        description="e.g. 'Physical Therapy Evaluation', 'Home Health Aide', 'Wound Care Supplies'",
    )
    frequency: str | None = Field(None, description="e.g. '3x/week for 4 weeks'")
    instructions: str | None = Field(
        None,
        description="Rx-style detail: quantity, schedule, special instructions, not captured by frequency",
    )


class ReferralIntake(BaseModel):
    # --- Patient identity & contact ---
    patient_name: str | None = None
    patient_dob: str | None = Field(None, description="MM/DD/YYYY if the source format is unambiguous, else as written")
    patient_sex: str | None = None
    patient_phone: str | None = None
    patient_address: str | None = None
    patient_mrn: str | None = Field(
        None, description="MRN, patient ID, or account # — whichever identifier the source uses"
    )

    # --- Referring / ordering source ---
    referring_provider_name: str | None = None
    referring_facility: str | None = None
    referring_phone: str | None = None
    referring_fax: str | None = None

    # --- Clinical ---
    diagnosis_text: str | None = Field(None, description="Free-text diagnosis or reason for referral")
    icd10_codes: list[str] = Field(default_factory=list)

    # --- Insurance ---
    insurance_provider: str | None = None
    insurance_id: str | None = Field(None, description="Policy / member / subscriber ID")
    insurance_group_number: str | None = None

    # --- Requested services ---
    requested_services: list[RequestedService] = Field(default_factory=list)

    # --- Dates ---
    referral_date: str | None = Field(None, description="Referral/order date, not the fax transmission timestamp")

    # --- Catch-all ---
    notes: str | None = Field(
        None,
        description=(
            "Anything clinically or administratively relevant that doesn't fit a structured "
            "field above: allergies, emergency contact, guarantor, employer, homebound "
            "justification, interpreter needs, etc."
        ),
    )

    # --- Extraction metadata (not from the document itself) ---
    source_file: str | None = Field(None, description="Filename this record was extracted from")
    pages_used: int | None = Field(None, description="How many pages of the source were sent to the model")

