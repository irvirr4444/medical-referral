from __future__ import annotations

from intake_extractor.aligned_intake import to_master_sheet_referral_from_canonical
from intake_extractor.canonical_referral import (
    CanonicalClinical,
    CanonicalDiagnosis,
    CanonicalReferral,
    CanonicalRequestedService,
    CanonicalSource,
    _ensure_core_quality,
    intake_clinical_summary,
)


def _clinical_record(
    clinical: CanonicalClinical,
    requested_services: list[CanonicalRequestedService] | None = None,
) -> CanonicalReferral:
    return CanonicalReferral(
        referral_id="ref_clinical",
        source=CanonicalSource(file_name="clinical.pdf", pdf_sha256="clinical"),
        clinical=clinical,
        requested_services=requested_services or [],
    )


def test_fay_like_uses_stage_description_without_invented_icd() -> None:
    clinical = CanonicalClinical(
        diagnoses=[CanonicalDiagnosis(description="Stage 2 coccyx wound", is_primary=True)],
    )

    summary = intake_clinical_summary(clinical)

    assert summary == "Stage 2 coccyx wound"
    assert "L89" not in summary


def test_zadran_like_joins_unstageable_pressure_ulcer_rows() -> None:
    clinical = CanonicalClinical(
        diagnoses=[
            CanonicalDiagnosis(
                description="Unstageable pressure ulcer of the sacral region",
                is_primary=True,
            ),
            CanonicalDiagnosis(description="Unstageable pressure ulcer of the left hip"),
        ],
    )

    assert intake_clinical_summary(clinical) == (
        "Unstageable pressure ulcer of the sacral region; "
        "Unstageable pressure ulcer of the left hip"
    )


def test_cruz_like_uses_requested_service_when_diagnoses_are_empty() -> None:
    clinical = CanonicalClinical()
    services = [CanonicalRequestedService(service="Wound care", instructions="Need wound care eval")]

    assert intake_clinical_summary(clinical, services) == "Need wound care eval"

    cleaned = _ensure_core_quality(_clinical_record(clinical, services))
    assert cleaned.clinical.summary == "Need wound care eval"
    assert cleaned.clinical.summary or cleaned.clinical.diagnoses or cleaned.clinical.notes


def test_cruz_like_drops_form_label_repeat_from_model_summary() -> None:
    clinical = CanonicalClinical(summary="Need wound care eval; Type of Care Needed: Wound Care")
    services = [
        CanonicalRequestedService(service="Wound Care (mobile service)", instructions="Need wound care eval")
    ]

    assert intake_clinical_summary(clinical, services) == "Need wound care eval"

    cleaned = _ensure_core_quality(_clinical_record(clinical, services))
    assert cleaned.clinical.summary == "Need wound care eval"
    monday = to_master_sheet_referral_from_canonical(cleaned)
    assert monday.diagnosis_text == "Need wound care eval"
    assert "Type of Care Needed" not in (monday.diagnosis_text or "")


def test_keeps_more_specific_short_summary_than_service_instruction() -> None:
    clinical = CanonicalClinical(summary="Need wound care eval of stage 2 heel ulcer")
    services = [CanonicalRequestedService(service="Wound Care", instructions="Need wound care eval")]

    assert intake_clinical_summary(clinical, services) == "Need wound care eval of stage 2 heel ulcer"


def test_butler_like_does_not_copy_comorbidity_list_to_monday() -> None:
    clinical = CanonicalClinical(
        diagnoses=[
            CanonicalDiagnosis(code="I25.10", description="ATHSCL HEART DISEASE OF NATIVE CORONARY ARTERY W/O ANG PCTRS"),
            CanonicalDiagnosis(code="I42.0", description="DILATED CARDIOMYOPATHY"),
            CanonicalDiagnosis(code="N18.31", description="CHRONIC KIDNEY DISEASE, STAGE 3A"),
        ],
        wound_order_included=False,
    )

    assert intake_clinical_summary(clinical) is None

    cleaned = _ensure_core_quality(_clinical_record(clinical))
    assert cleaned.clinical.summary is None
    assert cleaned.clinical.diagnoses

    monday = to_master_sheet_referral_from_canonical(cleaned)
    assert monday.diagnosis_text is None
    assert "CARDIOMYOPATHY" not in (monday.diagnosis_text or "")
    assert "CARDIOMYOPATHY" not in (monday.notes or "")
    assert monday.wound_order_included is False


def test_anita_like_replaces_narrative_with_surgical_wound_and_parks_notes() -> None:
    narrative = (
        "Patient was hospitalized at PIH Whittier from June 15 to June 29 for "
        "postoperative care. She requested wound care supplies and home health "
        "assistance for an abdominal surgical wound."
    )
    clinical = CanonicalClinical(
        summary=narrative,
        diagnoses=[CanonicalDiagnosis(description="Abdominal surgical wound with JP drain")],
    )

    summary = intake_clinical_summary(clinical)
    assert summary == "Abdominal surgical wound with JP drain"
    assert "PIH Whittier" not in summary

    cleaned = _ensure_core_quality(_clinical_record(clinical))
    assert cleaned.clinical.summary == "Abdominal surgical wound with JP drain"
    assert narrative in cleaned.clinical.notes

    monday = to_master_sheet_referral_from_canonical(cleaned)
    assert monday.diagnosis_text == "Abdominal surgical wound with JP drain"
    assert "PIH Whittier" not in (monday.notes or "")
    assert narrative not in (monday.notes or "")


def test_gonzalez_like_keeps_wound_rows_and_ignores_comorbidities() -> None:
    clinical = CanonicalClinical(
        diagnoses=[
            CanonicalDiagnosis(description="HIV"),
            CanonicalDiagnosis(description="Right groin unstageable pressure injury", is_primary=True),
            CanonicalDiagnosis(description="Wound cellulitis of the groin"),
            CanonicalDiagnosis(description="Anemia"),
        ],
    )

    summary = intake_clinical_summary(clinical)
    assert summary == (
        "Right groin unstageable pressure injury; Wound cellulitis of the groin"
    )
    assert "HIV" not in summary
    assert "Anemia" not in summary


def test_long_summary_without_wound_rows_becomes_first_sentence() -> None:
    narrative = (
        "Patient has a history of congestive heart failure, hypertension, and dementia "
        "and was admitted after a fall at home. Care team requested home health for "
        "medication management and a lengthy hospital course review."
    )
    clinical = CanonicalClinical(summary=narrative)

    summary = intake_clinical_summary(clinical)
    assert summary is not None
    assert summary.startswith("Patient has a history of congestive heart failure")
    assert "Care team requested" not in summary
    assert "lengthy hospital course" not in summary

    cleaned = _ensure_core_quality(_clinical_record(clinical))
    assert cleaned.clinical.summary == summary
    assert narrative in cleaned.clinical.notes
