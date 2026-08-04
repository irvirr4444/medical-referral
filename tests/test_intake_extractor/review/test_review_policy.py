import json
from pathlib import Path

from intake_extractor.review_tools.audit import build_document_audit, write_document_audit, write_folder_audit_summary
from intake_extractor.review_tools.patch import (
    apply_review_patches_with_decisions,
    patch_confidence_threshold,
)
from intake_extractor.models.review_schema import PredictionReview, ReviewIssue
from intake_extractor.review_tools.signals import collect_field_signals
from intake_extractor.review_tools.targets import TARGETED_REVIEW_FIELDS, get_field_policy
from intake_extractor.models.schema import ReferralIntake, RequestedService


def test_targeted_fields_cover_known_weak_areas() -> None:
    assert "requested_services" in TARGETED_REVIEW_FIELDS
    assert "diagnosis_text" in TARGETED_REVIEW_FIELDS
    assert get_field_policy("requested_services").tier == "flexible"
    assert get_field_policy("insurance_id").tier == "sensitive"


def test_sensitive_vs_flexible_thresholds_differ() -> None:
    sensitive = patch_confidence_threshold("insurance_id", "ABC123")
    flexible_missing = patch_confidence_threshold("referring_phone", None)
    flexible_suspicious = patch_confidence_threshold(
        "requested_services",
        [],
        suspicious_fields={"requested_services"},
    )

    assert sensitive >= 0.97
    assert flexible_missing < sensitive
    assert flexible_suspicious < flexible_missing


def test_diagnosis_replacement_requires_higher_confidence_than_services() -> None:
    services_threshold = patch_confidence_threshold("requested_services", [])
    diagnosis_threshold = patch_confidence_threshold(
        "diagnosis_text",
        "Long diagnosis text already present",
    )
    assert diagnosis_threshold > services_threshold
    assert diagnosis_threshold >= 0.9


def test_suspicious_facility_address_signal() -> None:
    candidate = ReferralIntake(
        referring_provider_name="Jane Doe, MD",
        referring_facility="123 Main Street, Chicago, IL 60601",
    ).model_dump(mode="json")

    signals = collect_field_signals(candidate)
    fields = {signal.field for signal in signals}

    assert "referring_facility" in fields


def test_suspicious_admin_requested_services_signal() -> None:
    candidate = ReferralIntake(
        pages_used=4,
        requested_services=[
            RequestedService(service="Follow-up appointment", instructions="Call clinic"),
            RequestedService(service="Wound Care"),
        ],
    ).model_dump(mode="json")

    signals = collect_field_signals(candidate)

    assert any(signal.field == "requested_services" for signal in signals)


def test_patch_acceptance_and_rejection_are_audited() -> None:
    candidate = ReferralIntake(
        referring_phone=None,
        insurance_id="ABC123",
    ).model_dump(mode="json")
    review = PredictionReview(
        overall_verdict="major_issues",
        summary="Mixed patches.",
        issues=[
            ReviewIssue(
                field="referring_phone",
                severity="major",
                predicted_value=None,
                suggest_patch=True,
                proposed_value="312-555-0101",
                confidence=0.86,
                problem="Missing referring phone.",
                evidence="Phone: 312-555-0101",
            ),
            ReviewIssue(
                field="insurance_id",
                severity="major",
                predicted_value="ABC123",
                suggest_patch=True,
                proposed_value="ABD123",
                confidence=0.97,
                problem="Possible OCR slip.",
                evidence="Member ID: ABD123",
            ),
        ],
    )

    patched, applied, decisions = apply_review_patches_with_decisions(candidate, review)

    assert patched["referring_phone"] == "312-555-0101"
    assert patched["insurance_id"] == "ABC123"
    assert [patch.field for patch in applied] == ["referring_phone"]
    assert any(d.field == "referring_phone" and d.applied for d in decisions)
    assert any(d.field == "insurance_id" and not d.applied for d in decisions)
    assert any("below threshold" in d.reason for d in decisions if d.field == "insurance_id")


def test_suspicious_bonus_can_accept_flexible_patch() -> None:
    candidate = ReferralIntake(requested_services=[]).model_dump(mode="json")
    review = PredictionReview(
        overall_verdict="major_issues",
        summary="Missing ordered wound care.",
        issues=[
            ReviewIssue(
                field="requested_services",
                severity="major",
                predicted_value=[],
                suggest_patch=True,
                proposed_value=[{"service": "Wound Care", "frequency": None, "instructions": None}],
                confidence=0.71,
                problem="Wound care checkbox is checked.",
                evidence="Requested Services: Wound Care",
            )
        ],
    )

    # Empty-list threshold is ~0.73; suspicious bonus lowers it to the 0.70 floor.
    _patched_plain, applied_plain, _ = apply_review_patches_with_decisions(candidate, review)
    patched_flagged, applied_flagged, decisions = apply_review_patches_with_decisions(
        candidate,
        review,
        suspicious_fields={"requested_services"},
    )

    assert applied_plain == []
    assert applied_flagged
    assert patched_flagged["requested_services"][0]["service"] == "Wound Care"
    assert decisions[0].applied is True


def test_audit_artifact_generation(tmp_path: Path) -> None:
    candidate = ReferralIntake(referring_facility=None).model_dump(mode="json")
    review = PredictionReview(
        source_file="demo.pdf",
        overall_verdict="major_issues",
        summary="Facility missing.",
        issues=[
            ReviewIssue(
                field="referring_facility",
                severity="major",
                predicted_value=None,
                suggest_patch=True,
                proposed_value="Accent Care Home Health",
                confidence=0.9,
                problem="Facility listed in header.",
                evidence="From: Accent Care Home Health",
            )
        ],
    )
    _, _, decisions = apply_review_patches_with_decisions(candidate, review)
    signals = collect_field_signals(candidate)
    audit = build_document_audit(
        source_file="demo.pdf",
        candidate=candidate,
        review=review,
        decisions=decisions,
        signals=signals,
        reviewed_fields=list(TARGETED_REVIEW_FIELDS),
    )

    write_document_audit(tmp_path, "demo", review, audit)
    write_folder_audit_summary(tmp_path, [audit])

    review_path = tmp_path / "demo.review.json"
    applied_path = tmp_path / "demo.applied_patches.json"
    audit_path = tmp_path / "demo.audit.json"
    summary_path = tmp_path / "audit_summary.json"

    assert review_path.exists()
    assert applied_path.exists()
    assert audit_path.exists()
    assert summary_path.exists()

    applied_payload = json.loads(applied_path.read_text(encoding="utf-8"))
    audit_payload = json.loads(audit_path.read_text(encoding="utf-8"))
    assert applied_payload[0]["field"] == "referring_facility"
    assert audit_payload["applied_count"] == 1
    assert "referring_facility" in audit_payload["reviewed_fields"]
