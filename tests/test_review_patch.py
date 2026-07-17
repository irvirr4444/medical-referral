from intake_extractor.review_patch import apply_review_patches, patch_confidence_threshold
from intake_extractor.repair import merge_repair_payload
from intake_extractor.review_schema import PredictionReview, ReviewIssue
from intake_extractor.schema import ReferralIntake, RequestedService


def test_apply_review_patches_updates_flexible_field_with_high_confidence() -> None:
    candidate = ReferralIntake(referring_phone=None).model_dump(mode="json")
    review = PredictionReview(
        overall_verdict="major_issues",
        summary="Missing referring phone.",
        issues=[
            ReviewIssue(
                field="referring_phone",
                severity="major",
                predicted_value=None,
                suggest_patch=True,
                proposed_value="312-555-0101",
                confidence=0.88,
                expected_value="312-555-0101",
                problem="The referral header lists a phone number.",
                evidence="Phone: 312-555-0101",
            )
        ],
    )

    patched, applied = apply_review_patches(candidate, review)

    assert patched["referring_phone"] == "312-555-0101"
    assert [patch.field for patch in applied] == ["referring_phone"]


def test_apply_review_patches_requires_extra_confidence_for_sensitive_replacement() -> None:
    candidate = ReferralIntake(insurance_id="ABC123").model_dump(mode="json")
    review = PredictionReview(
        overall_verdict="major_issues",
        summary="Insurance ID mismatch.",
        issues=[
            ReviewIssue(
                field="insurance_id",
                severity="major",
                predicted_value="ABC123",
                suggest_patch=True,
                proposed_value="ABD123",
                confidence=0.97,
                expected_value="ABD123",
                problem="The final digit is D, not C.",
                evidence="Member ID: ABD123",
            )
        ],
    )

    patched, applied = apply_review_patches(candidate, review)

    assert patched["insurance_id"] == "ABC123"
    assert applied == []
    assert patch_confidence_threshold("insurance_id", "ABC123") == 0.99


def test_apply_review_patches_can_clear_flexible_field() -> None:
    candidate = ReferralIntake(referring_provider_name="General Hospital").model_dump(mode="json")
    review = PredictionReview(
        overall_verdict="minor_issues",
        summary="Facility placed in provider field.",
        issues=[
            ReviewIssue(
                field="referring_provider_name",
                severity="minor",
                predicted_value="General Hospital",
                suggest_patch=True,
                proposed_value=None,
                confidence=0.9,
                expected_value=None,
                problem="No individual ordering clinician is listed.",
                evidence="Only facility name appears in the referral header.",
            )
        ],
    )

    patched, applied = apply_review_patches(candidate, review)

    assert patched["referring_provider_name"] is None
    assert len(applied) == 1


def test_apply_review_patches_respects_suggest_patch_flag() -> None:
    candidate = ReferralIntake(patient_address="123 Main St").model_dump(mode="json")
    review = PredictionReview(
        overall_verdict="minor_issues",
        summary="Address may be incomplete.",
        issues=[
            ReviewIssue(
                field="patient_address",
                severity="minor",
                predicted_value="123 Main St",
                suggest_patch=False,
                proposed_value="123 Main St, Chicago, IL 60601",
                confidence=0.99,
                expected_value="123 Main St, Chicago, IL 60601",
                problem="The city/state/ZIP may be missing, but the source is fuzzy.",
                evidence="Address text is partially obscured.",
            )
        ],
    )

    patched, applied = apply_review_patches(candidate, review)

    assert patched["patient_address"] == "123 Main St"
    assert applied == []


def test_apply_review_patches_skips_invalid_requested_services_shape() -> None:
    candidate = ReferralIntake(
        requested_services=[RequestedService(service="Wound Care")]
    ).model_dump(mode="json")
    review = PredictionReview(
        overall_verdict="major_issues",
        summary="Requested services shape is wrong.",
        issues=[
            ReviewIssue(
                field="requested_services",
                severity="major",
                predicted_value=[{"service": "Wound Care"}],
                suggest_patch=True,
                proposed_value="Wound Care",
                confidence=0.95,
                expected_value="[{\"service\": \"Wound Care\"}]",
                problem="The reviewer proposed the wrong type.",
                evidence="Requested services are listed as structured rows.",
            )
        ],
    )

    patched, applied = apply_review_patches(candidate, review)

    assert patched["requested_services"] == [{"service": "Wound Care", "frequency": None, "instructions": None}]
    assert applied == []


def test_merge_repair_payload_keeps_richer_requested_services_at_same_length() -> None:
    primary = ReferralIntake(
        requested_services=[RequestedService(service="Wound Care", instructions="Eval")]
    )

    merged = merge_repair_payload(
        primary,
        {
            "requested_services": [
                {
                    "service": "Wound Care",
                    "frequency": "3x/week",
                    "instructions": "Eval and treat coccyx wound",
                }
            ]
        },
    )

    assert merged.requested_services == [
        RequestedService(service="Wound Care", frequency="3x/week", instructions="Eval and treat coccyx wound")
    ]
