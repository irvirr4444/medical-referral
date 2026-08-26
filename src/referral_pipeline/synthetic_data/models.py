"""Validated source records for realistic synthetic referral packets."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


def _parse_flexible_date(value: str) -> datetime:
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y", "%m.%d.%Y"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f"unrecognized date format: {value}")


class SyntheticService(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service: str
    frequency: str | None = None
    instructions: str | None = None


class SyntheticReferral(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str
    layout: Literal[
        "patient_chart",
        "wcw_handwritten",
        "hospital_fax",
        "hospital_facesheet",
        "home_health_fax",
        "discharge_packet",
        "agency_summary",
    ]
    scenario: str
    scan_style: Literal["clean", "fax"]
    patient_name: str
    patient_dob: str
    patient_sex: Literal["Female", "Male"]
    patient_phone: str | None
    patient_address: str | None
    patient_mrn: str
    referral_date: str
    admission_date: str | None = None
    referring_facility: str
    referring_provider_name: str
    referring_phone: str
    referring_fax: str
    diagnosis_text: str | None
    icd10_codes: list[str] = Field(default_factory=list)
    insurance_provider: str | None
    insurance_id: str | None
    insurance_group_number: str | None = None
    requested_services: list[SyntheticService] = Field(default_factory=list)
    emergency_contact: str | None = None
    expected_outcome: Literal[
        "ready_for_human_approval",
        "manual_review_required",
        "blocked_missing_threshold",
    ]
    expected_monday_duplicate: Literal["no_candidates_found", "duplicate_found"]
    expected_drk_duplicate: Literal["clear_to_create", "duplicate_found", "manual_review_required"]

    @model_validator(mode="after")
    def validate_consistency(self) -> "SyntheticReferral":
        dob = _parse_flexible_date(self.patient_dob)
        referral = _parse_flexible_date(self.referral_date)
        if dob >= referral:
            raise ValueError("patient DOB must precede the referral date")
        if self.admission_date:
            admitted = _parse_flexible_date(self.admission_date)
            if admitted > referral and self.scenario != "conflicting_dates":
                raise ValueError("admission date cannot follow the referral date")
        if self.expected_outcome == "blocked_missing_threshold" and all(
            (self.patient_name, self.patient_dob, self.patient_phone, self.patient_address)
        ):
            raise ValueError("blocked threshold scenario must omit phone or address")
        return self

    def gold_record(self, filename: str) -> dict[str, object]:
        services = [item.model_dump(mode="json") for item in self.requested_services]
        notes = [
            "SYNTHETIC TEST DATA - NOT A REAL PATIENT.",
            f"Scenario: {self.scenario}.",
        ]
        if self.emergency_contact:
            notes.append(f"Emergency contact: {self.emergency_contact}.")
        return {
            "patient_name": self.patient_name,
            "patient_dob": self.patient_dob,
            "patient_sex": self.patient_sex,
            "patient_phone": self.patient_phone,
            "patient_address": self.patient_address,
            "patient_mrn": self.patient_mrn,
            "referral_date": self.referral_date,
            "referring_facility": self.referring_facility,
            "referring_provider_name": self.referring_provider_name,
            "referring_phone": self.referring_phone,
            "referring_fax": self.referring_fax,
            "diagnosis_text": self.diagnosis_text,
            "icd10_codes": self.icd10_codes,
            "insurance_provider": self.insurance_provider,
            "insurance_id": self.insurance_id,
            "insurance_group_number": self.insurance_group_number,
            "requested_services": services,
            "notes": " ".join(notes),
            "source_file": filename,
        }
