from intake_extractor.extraction_evidence import (
    ExtractionEvidenceGuide,
    apply_evidence_guide,
    needs_exact_field_evidence,
    prepend_evidence_guide,
)
from intake_extractor.schema import ReferralIntake


def test_prepend_evidence_guide_adds_grounding_block() -> None:
    guide = ExtractionEvidenceGuide.model_validate(
        {
            "sections": {"requested_services_block": "Order: skilled nursing eval"},
            "exact_fields": {"insurance_id": "ABC12345"},
            "notes": ["multiple phone numbers listed"],
        }
    )

    content = prepend_evidence_guide([{"type": "text", "text": "INPUT TYPE: IMAGES"}], guide)

    assert content[0]["type"] == "text"
    assert "EVIDENCE GUIDE" in content[0]["text"]
    assert "requested_services_block" in content[0]["text"]
    assert "insurance_id: ABC12345" in content[0]["text"]


def test_prepend_evidence_guide_can_limit_scope() -> None:
    guide = ExtractionEvidenceGuide.model_validate(
        {
            "sections": {
                "requested_services_block": "Order: skilled nursing eval",
                "insurance_block": "Member ID ABC12345",
            },
            "exact_fields": {"insurance_id": "ABC12345"},
            "notes": ["multiple phone numbers listed"],
        }
    )

    content = prepend_evidence_guide(
        [{"type": "text", "text": "INPUT TYPE: IMAGES"}],
        guide,
        include_exact_fields=(),
        include_section_fields=("requested_services_block",),
        include_notes=False,
        header="REQUESTED SERVICES GUIDE",
    )

    assert "REQUESTED SERVICES GUIDE" in content[0]["text"]
    assert "requested_services_block" in content[0]["text"]
    assert "insurance_id" not in content[0]["text"]
    assert "multiple phone numbers listed" not in content[0]["text"]


def test_apply_evidence_guide_replaces_ambiguous_exact_fields() -> None:
    guide = ExtractionEvidenceGuide.model_validate(
        {
            "sections": {},
            "exact_fields": {
                "patient_phone": "(626) 379-1461",
                "referring_phone": "(303) 993-1330",
                "insurance_id": "6TX4F45XH02",
            },
            "notes": [],
        }
    )
    referral = ReferralIntake(
        patient_phone="home (626) 379-1461, mobile (626) 524-2856",
        referring_phone=None,
        insurance_id="WTX4F45X#02",
    )

    updated = apply_evidence_guide(referral, guide)

    assert updated.patient_phone == "(626) 379-1461"
    assert updated.referring_phone == "(303) 993-1330"
    assert updated.insurance_id == "6TX4F45XH02"


def test_needs_exact_field_evidence_flags_ambiguous_values() -> None:
    referral = ReferralIntake(
        patient_phone="home (626) 379-1461, mobile (626) 524-2856",
        insurance_id="WTX4F45X#02",
    )

    assert needs_exact_field_evidence(referral) is True


def test_needs_exact_field_evidence_skips_clean_values() -> None:
    referral = ReferralIntake(
        patient_name="BUTLER, ALVA",
        patient_phone="(260) 438-4646",
        referring_phone="(310) 303-6859",
        referring_fax="(303) 647-3647",
        insurance_id="4FM5A30MN88",
    )

    assert needs_exact_field_evidence(referral) is False
