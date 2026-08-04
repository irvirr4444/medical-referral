from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from drk_emr.create_patient.schema import (
    DrkAddressDraft,
    DrkAdmissionDraft,
    DrkContactDraft,
    DrkCreateDraftEnvelope,
    DrkCreatePayloadDraft,
    DrkDemographicsDraft,
    DrkEmergencyContactDraft,
    DrkInsuranceDraft,
    DrkReferralDraft,
    DrkSubscriberDraft,
)

from .canonical_referral import CanonicalReferral
from .drk_pdf_schema import (
    AdmissionCandidate,
    AllergyCandidate,
    DiagnosisCandidate,
    DrkPdfExtraction,
    InsuranceCandidate,
    MedicationCandidate,
    PatientCandidate,
    ReferringSourceCandidate,
    RequestedServiceCandidate,
)
from .models.schema import ReferralIntake, RequestedService


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AlignedSource(StrictModel):
    file_name: str
    file_sha256: str
    file_size_bytes: int
    page_count: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class HandoffReadiness(StrictModel):
    seven_field_ready: bool
    seven_field_missing: list[str] = Field(default_factory=list)
    seven_field_status: dict[str, str] = Field(default_factory=dict)
    monday_threshold_ready: bool
    monday_threshold_missing: list[str] = Field(default_factory=list)
    drk_fill_ready: bool
    drk_blockers: list[str] = Field(default_factory=list)
    handoff_mode: str = "parallel_after_human_approval"
    targets: list[str] = Field(default_factory=lambda: ["monday_master_sheet", "drk_patient"])
    requires_human_approval: bool = True


class AlignedIntakeBundle(StrictModel):
    version: int = 1
    correlation_id: str
    source: AlignedSource
    canonical_referral: CanonicalReferral
    master_sheet_referral: ReferralIntake
    drk_create_draft: DrkCreateDraftEnvelope
    readiness: HandoffReadiness


def build_aligned_intake_bundle(
    canonical: CanonicalReferral,
    pdf_path: str | Path,
    *,
    source_metadata: dict[str, Any] | None = None,
    page_count: int | None = None,
) -> AlignedIntakeBundle:
    pdf = Path(pdf_path)
    digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
    if page_count is None:
        evidence_pages = {
            page
            for quality in canonical.field_quality.values()
            for page in quality.evidence_pages
        }
        page_count = max(evidence_pages) if evidence_pages else None
    extraction = _legacy_projection(canonical)
    master_sheet_referral = to_master_sheet_referral_from_canonical(canonical)
    drk_create_draft = to_drk_create_draft(extraction)
    threshold_fields = {
        "patient_name": master_sheet_referral.patient_name,
        "patient_dob": master_sheet_referral.patient_dob,
        "patient_phone": master_sheet_referral.patient_phone,
        "patient_address": master_sheet_referral.patient_address,
    }
    threshold_missing = [field for field, value in threshold_fields.items() if not value]
    seven_paths = (
        "patient.name",
        "patient.date_of_birth",
        "patient.phones",
        "patient.address",
        "home_health_or_hospice",
        "clinical",
        "insurances",
    )
    seven_status = {
        path: canonical.field_quality[path].status if path in canonical.field_quality else "missing"
        for path in seven_paths
    }
    seven_missing = [
        path for path, status in seven_status.items() if status not in {"present", "explicitly_none"}
    ]
    return AlignedIntakeBundle(
        correlation_id=f"pdf-{digest[:24]}",
        source=AlignedSource(
            file_name=pdf.name,
            file_sha256=digest,
            file_size_bytes=pdf.stat().st_size,
            page_count=page_count,
            metadata=source_metadata or {},
        ),
        canonical_referral=canonical,
        master_sheet_referral=master_sheet_referral,
        drk_create_draft=drk_create_draft,
        readiness=HandoffReadiness(
            seven_field_ready=not seven_missing,
            seven_field_missing=seven_missing,
            seven_field_status=seven_status,
            monday_threshold_ready=not threshold_missing,
            monday_threshold_missing=threshold_missing,
            drk_fill_ready=drk_create_draft.ready_for_fill,
            drk_blockers=drk_create_draft.blockers,
        ),
    )


def _legacy_projection(canonical: CanonicalReferral) -> DrkPdfExtraction:
    """Project the canonical record into the existing low-level DRK card shape."""
    patient = canonical.patient
    phones = patient.phones
    emergency = patient.emergency_contact
    return DrkPdfExtraction(
        document_type=canonical.document_type,
        patient=PatientCandidate(
            first_name=patient.name.first,
            middle_name=patient.name.middle,
            last_name=patient.name.last,
            full_name=patient.name.full,
            source_patient_id=patient.source_patient_id,
            source_patient_id_label=patient.source_patient_id_label,
            mrn=patient.mrn,
            ssn=patient.ssn,
            date_of_birth=patient.date_of_birth,
            age=patient.age,
            gender=patient.sex_or_gender,
            address1=patient.address.line_1,
            address2=patient.address.line_2,
            city=patient.address.city,
            state=patient.address.state,
            zip_code=patient.address.postal_code,
            phone_number=phones[0].number if phones else None,
            secondary_phone_number=phones[1].number if len(phones) > 1 else None,
            email=patient.email,
            emergency_contact_name=None if emergency is None else emergency.name.full,
            emergency_contact_phone=None if emergency is None else emergency.phone,
        ),
        referring_source=ReferringSourceCandidate(
            provider_name=canonical.referral_source.provider_name,
            facility_name=canonical.referral_source.organization.name,
            phone=canonical.referral_source.organization.phone,
            fax=canonical.referral_source.organization.fax,
            address=canonical.referral_source.organization.address,
            referral_date=canonical.referral_source.referral_or_order_date,
        ),
        admission=AdmissionCandidate(
            admission_date=canonical.admission.admission_date,
            facility_name=canonical.admission.facility.name,
            facility_phone=canonical.admission.facility.phone,
            facility_fax=canonical.admission.facility.fax,
            home_health_company=canonical.home_health_or_hospice.organization.name,
            place_of_service=canonical.admission.place_of_service,
            medicare_admission=canonical.admission.medicare_admission,
            palliative_admission=canonical.home_health_or_hospice.palliative_care,
            hospice=canonical.home_health_or_hospice.hospice,
        ),
        diagnoses_section_present=canonical.clinical.diagnoses_section_present,
        diagnoses=[DiagnosisCandidate(**item.model_dump()) for item in canonical.clinical.diagnoses],
        medications_section_present=canonical.clinical.medications_section_present,
        medications=[MedicationCandidate(**item.model_dump()) for item in canonical.clinical.medications],
        allergies_section_present=canonical.clinical.allergies_section_present,
        no_known_allergies_explicit=True if canonical.clinical.no_known_allergies_explicit is True else None,
        allergies=[AllergyCandidate(**item.model_dump()) for item in canonical.clinical.allergies],
        insurance_section_present=(
            canonical.field_quality.get("insurances").status in {"present", "explicitly_none"}
            if canonical.field_quality.get("insurances")
            else None
        ),
        insurances=[InsuranceCandidate(**item.model_dump()) for item in canonical.insurances],
        requested_services=[RequestedServiceCandidate(**item.model_dump()) for item in canonical.requested_services],
        other_clinical_notes=[
            *([canonical.clinical.summary] if canonical.clinical.summary else []),
            *canonical.clinical.notes,
            *(
                [f"Wound order explicitly included: {'Yes' if canonical.clinical.wound_order_included else 'No'}"]
                if canonical.clinical.wound_order_included is not None
                else []
            ),
        ],
        warnings=canonical.warnings,
    )


def to_master_sheet_referral_from_canonical(canonical: CanonicalReferral) -> ReferralIntake:
    referral = to_master_sheet_referral(_legacy_projection(canonical), source_file=canonical.source.file_name)
    source = canonical.referral_source.organization
    return referral.model_copy(
        update={
            "referring_facility": source.name,
            "agency_contact_name": source.contact_name,
            "agency_email": source.email,
            "diagnosis_text": canonical.clinical.summary or referral.diagnosis_text,
        }
    )


def to_drk_create_draft_from_canonical(canonical: CanonicalReferral) -> DrkCreateDraftEnvelope:
    return to_drk_create_draft(_legacy_projection(canonical))


def to_master_sheet_referral(
    extraction: DrkPdfExtraction,
    *,
    source_file: str | None = None,
) -> ReferralIntake:
    patient = extraction.patient
    first_name, last_name, full_name = _patient_names(extraction)
    address = _full_address(extraction)
    agency = extraction.referring_source.facility_name
    diagnosis_descriptions = [
        item.description or item.code
        for item in extraction.diagnoses
        if item.description or item.code
    ]
    diagnosis_text = _bounded_join(diagnosis_descriptions, limit=1800)
    icd10_codes = _dedupe([item.code for item in extraction.diagnoses if item.code])
    insurance = extraction.insurances[0] if extraction.insurances else None
    notes = _master_sheet_notes(extraction)
    requested_services = [
        RequestedService(
            service=item.service,
            frequency=item.frequency,
            instructions=item.instructions,
        )
        for item in extraction.requested_services
    ]
    return ReferralIntake(
        patient_name=full_name or " ".join(part for part in (first_name, last_name) if part) or None,
        patient_dob=_iso_date(patient.date_of_birth),
        patient_sex=patient.gender,
        patient_phone=patient.phone_number,
        patient_email=patient.email,
        patient_address=address,
        patient_mrn=patient.mrn,
        referring_provider_name=extraction.referring_source.provider_name,
        referring_facility=agency,
        referring_phone=extraction.referring_source.phone,
        referring_fax=extraction.referring_source.fax,
        current_home_health_or_hospice=extraction.admission.home_health_company,
        place_of_service=extraction.admission.place_of_service,
        wound_order_included=_wound_order_value(extraction.other_clinical_notes),
        diagnosis_text=diagnosis_text,
        icd10_codes=icd10_codes,
        insurance_provider=None if insurance is None else insurance.payer_name,
        insurance_id=None if insurance is None else insurance.policy_number,
        insurance_group_number=None if insurance is None else insurance.group_number,
        requested_services=requested_services,
        referral_date=_iso_date(extraction.referring_source.referral_date),
        notes=notes,
        source_file=source_file,
        pages_used=_evidence_page_count(extraction),
    )


def to_drk_create_draft(extraction: DrkPdfExtraction) -> DrkCreateDraftEnvelope:
    patient = extraction.patient
    first_name, last_name, _ = _patient_names(extraction)
    emergency_first, emergency_last = _split_person_name(patient.emergency_contact_name)
    gender = _drk_gender(patient.gender)
    admission = extraction.admission
    unresolved: list[str] = []
    warnings: list[str] = []

    place_query = _clean(admission.place_of_service)
    facility_query = _clean(admission.facility_name)
    home_health_query = _clean(admission.home_health_company)
    for field, value in (
        ("admission.place_of_service_query", place_query),
        ("admission.facility_query", facility_query),
        ("admission.home_health_query", home_health_query),
    ):
        if value:
            unresolved.append(f"{field}:requires_exact_drk_catalog_match")

    insurances: list[DrkInsuranceDraft] = []
    for index, insurance in enumerate(extraction.insurances):
        insurance_type = insurance.insurance_type if insurance.insurance_type in {"Primary", "Secondary", "Tertiary"} else None
        payer_query = _clean(insurance.payer_name)
        if payer_query:
            unresolved.append(f"insurances[{index}].payer_query:requires_exact_drk_catalog_match")
        if insurance.insurance_type and insurance_type is None:
            unresolved.append(f"insurances[{index}].insurance_type:unsupported_or_unresolved")
        subscriber = None
        if insurance.is_patient_policy_holder is False or insurance.subscriber_first_name or insurance.subscriber_last_name:
            subscriber = DrkSubscriberDraft(
                first_name=insurance.subscriber_first_name,
                last_name=insurance.subscriber_last_name,
                date_of_birth=_iso_date(insurance.subscriber_date_of_birth),
                relationship_to_patient=insurance.subscriber_relationship,
            )
        insurances.append(
            DrkInsuranceDraft(
                payer_query=payer_query,
                insurance_type=insurance_type,
                policy_number=insurance.policy_number,
                group_number=insurance.group_number,
                group_name=insurance.group_name,
                effective_date=_iso_date(insurance.effective_date),
                termination_date=_iso_date(insurance.expiration_date),
                is_patient_policy_holder=insurance.is_patient_policy_holder,
                subscriber=subscriber,
            )
        )

    if extraction.referring_source.provider_name:
        warnings.append(
            "Clinical referring provider was preserved but not used as DRK provider_query; an exact DRK provider match is required."
        )
    if extraction.referring_source.facility_name:
        warnings.append(
            "Clinical referring facility is not automatically treated as the patient's DRK admission facility."
        )

    payload = DrkCreatePayloadDraft(
        demographics=DrkDemographicsDraft(
            first_name=first_name,
            middle_name=patient.middle_name,
            last_name=last_name,
            date_of_birth=_iso_date(patient.date_of_birth),
            gender=gender,
            ssn=patient.ssn,
        ),
        primary_address=DrkAddressDraft(
            address_line_1=patient.address1,
            address_line_2=patient.address2,
            city=patient.city,
            state=patient.state,
            zip_code=patient.zip_code,
            country="United States" if patient.state else None,
        ),
        contact=DrkContactDraft(
            primary_phone=patient.phone_number,
            secondary_phone=patient.secondary_phone_number,
            email=patient.email,
        ),
        emergency_contact=DrkEmergencyContactDraft(
            first_name=emergency_first,
            last_name=emergency_last,
            phone=patient.emergency_contact_phone,
        ),
        admission=DrkAdmissionDraft(
            admission_date=_iso_date(admission.admission_date),
            place_of_service_query=place_query,
            facility_query=facility_query,
            home_health_query=home_health_query,
            medicare_admission=admission.medicare_admission,
            palliative_care=admission.palliative_admission,
            hospice=admission.hospice,
        ),
        referral=DrkReferralDraft(
            referral_date=_iso_date(extraction.referring_source.referral_date),
            clinical_referring_provider=extraction.referring_source.provider_name,
            clinical_referring_facility=extraction.referring_source.facility_name,
        ),
        insurances=insurances,
    )
    required = {
        "demographics.first_name": first_name,
        "demographics.last_name": last_name,
        "demographics.ssn": payload.demographics.ssn,
        "demographics.date_of_birth": payload.demographics.date_of_birth,
        "demographics.gender": payload.demographics.gender,
        "contact.primary_phone": payload.contact.primary_phone,
        "primary_address.address_line_1": payload.primary_address.address_line_1,
        "primary_address.city": payload.primary_address.city,
        "primary_address.state": payload.primary_address.state,
        "primary_address.zip_code": payload.primary_address.zip_code,
    }
    blockers = [f"missing_required:{field}" for field, value in required.items() if not value]
    if not insurances:
        blockers.append("missing_required:insurances")
    for index, insurance in enumerate(insurances):
        if not insurance.payer_query:
            blockers.append(f"missing_required:insurances[{index}].payer_query")
        if not insurance.insurance_type:
            blockers.append(f"missing_required:insurances[{index}].insurance_type")
        if not insurance.policy_number:
            blockers.append(f"missing_required:insurances[{index}].policy_number")
    blockers.extend(f"unresolved_catalog:{item}" for item in unresolved)
    return DrkCreateDraftEnvelope(
        payload=payload,
        ready_for_fill=not blockers,
        blockers=blockers,
        unresolved_fields=unresolved,
        warnings=warnings,
    )


def _patient_names(extraction: DrkPdfExtraction) -> tuple[str | None, str | None, str | None]:
    patient = extraction.patient
    first = _clean(patient.first_name)
    last = _clean(patient.last_name)
    full = _clean(patient.full_name)
    if full and (not first or not last):
        if "," in full:
            family, given = [part.strip() for part in full.split(",", 1)]
            last = last or family
            first = first or (given.split()[0] if given else None)
        else:
            parts = full.split()
            first = first or (parts[0] if parts else None)
            last = last or (parts[-1] if len(parts) > 1 else None)
    if not full:
        full = " ".join(part for part in (first, _clean(patient.middle_name), last) if part) or None
    return first, last, full


def _split_person_name(value: str | None) -> tuple[str | None, str | None]:
    cleaned = _clean(value)
    if not cleaned:
        return None, None
    if "," in cleaned:
        last, first = [part.strip() for part in cleaned.split(",", 1)]
        return first or None, last or None
    parts = cleaned.split()
    if len(parts) == 1:
        return parts[0], None
    return parts[0], parts[-1]


def _full_address(extraction: DrkPdfExtraction) -> str | None:
    patient = extraction.patient
    locality = " ".join(part for part in (patient.city, patient.state, patient.zip_code) if part)
    return " ".join(part for part in (patient.address1, patient.address2, locality) if part) or None


def _drk_gender(value: str | None) -> str | None:
    cleaned = _clean(value)
    if not cleaned:
        return None
    aliases = {"m": "Male", "male": "Male", "f": "Female", "female": "Female"}
    exact = {
        "Male",
        "Female",
        "Male-to-Female",
        "Female-to-Male",
        "Genderqueer",
        "Unknown",
        "Other",
    }
    return aliases.get(cleaned.lower()) or (cleaned if cleaned in exact else None)


def _iso_date(value: str | None) -> str | None:
    cleaned = _clean(value)
    if not cleaned:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%m/%d/%Y", "%m/%d/%y", "%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(cleaned, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _master_sheet_notes(extraction: DrkPdfExtraction) -> str | None:
    notes: list[str] = []
    patient = extraction.patient
    if patient.source_patient_id:
        label = patient.source_patient_id_label or "source patient ID"
        notes.append(f"{label}: {patient.source_patient_id}")
    if extraction.admission.hospice is True:
        notes.append("Hospice indicated in referral.")
    if extraction.allergies:
        allergy_names = [item.name for item in extraction.allergies if item.name]
        if allergy_names:
            notes.append("Allergies: " + ", ".join(allergy_names))
    elif extraction.no_known_allergies_explicit is True:
        notes.append("Document explicitly states no known allergies.")
    if extraction.medications:
        notes.append(f"Medication list present ({len(extraction.medications)} entries); see canonical extraction.")
    if len(extraction.insurances) > 1:
        extras = [
            " / ".join(part for part in (item.payer_name, item.policy_number) if part)
            for item in extraction.insurances[1:]
        ]
        notes.append("Additional insurance: " + "; ".join(item for item in extras if item))
    notes.extend(extraction.other_clinical_notes)
    return _bounded_join(notes, limit=1800)


def _wound_order_value(notes: list[str]) -> bool | None:
    for note in notes:
        if note == "Wound order explicitly included: Yes":
            return True
        if note == "Wound order explicitly included: No":
            return False
    return None


def _bounded_join(values: list[str], *, limit: int) -> str | None:
    cleaned = [_clean(value) for value in values]
    parts = [value for value in cleaned if value]
    if not parts:
        return None
    result = "; ".join(parts)
    return result if len(result) <= limit else result[: limit - 3].rstrip() + "..."


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = _clean(value)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def _evidence_page_count(extraction: DrkPdfExtraction) -> int | None:
    pages = {page for evidence in extraction.evidence for page in evidence.page_numbers}
    return len(pages) if pages else None


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(str(value).split())
    return cleaned or None
