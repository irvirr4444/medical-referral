from __future__ import annotations

import json

from referral_pipeline.review.summary import render_review_email


def _write(path, value) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def test_summary_separates_general_monday_and_drk_data(tmp_path) -> None:
    canonical = tmp_path / "canonical.json"
    monday = tmp_path / "monday.json"
    plan = tmp_path / "plan.json"
    drk = tmp_path / "drk.json"
    config = tmp_path / "config.json"
    _write(
        canonical,
        {
            "source": {"file_name": "synthetic.pdf"},
            "patient": {
                "name": {"full": "TEST Jamie Tester"},
                "date_of_birth": "1958-01-15",
                "phones": [{"number": "555-0100"}],
                "address": {"line_1": "1 Test Way", "city": "Fresno", "state": "CA"},
            },
            "referral_source": {"organization": {"name": "Synthetic Home Health"}, "referral_or_order_date": "2026-08-04"},
            "home_health_or_hospice": {"organization": {"name": "Synthetic Home Health"}},
            "clinical": {"summary": "Synthetic wound referral"},
            "insurances": [{"payer_name": "Synthetic Payer", "policy_number": "TEST-1"}],
            "requested_services": [{"service": "Wound Care"}],
            "field_quality": {"patient.name": {"status": "present", "confidence": "high"}},
            "warnings": [],
        },
    )
    _write(
        monday,
        {"item_name": "TEST Jamie Tester", "column_values": {"date12": {"date": "1958-01-15"}}, "mapping_notes": [], "blocked": False, "blockers": []},
    )
    _write(plan, {"outcome": "ready_for_human_approval", "review_reasons": [], "monday_duplicate_check": {"status": "no_candidates_found", "candidates": []}})
    _write(
        drk,
        {"ready_for_fill": False, "blockers": ["missing_required:ssn"], "unresolved_fields": [], "payload": {"demographics": {"first_name": "Jamie"}}},
    )
    _write(config, {"columns": {"patient_dob": "date12"}, "column_titles": {"patient_dob": "Patient DoB"}})

    subject, body = render_review_email(
        review_id="review_abc123_xyz987",
        token="abcdefghijklmnop",
        canonical_path=canonical,
        intake_plan_path=plan,
        monday_preview_path=monday,
        drk_draft_path=drk,
        write_config_path=config,
    )

    assert "TEST Jamie Tester" not in subject
    assert "GENERAL REFERRAL SUMMARY" in body
    assert "MONDAY.COM PROPOSED WRITE" in body
    assert "Patient DoB" in body
    assert "Monday duplicate status: no_candidates_found" in body
    assert "DRK PROPOSED PATIENT DATA" in body
    assert "pending the existing guarded" not in body
    assert "CONFIRMED review_abc123_xyz987 abcdefghijklmnop" in body


def test_blocked_summary_does_not_include_approval_command(tmp_path) -> None:
    canonical = tmp_path / "canonical.json"
    plan = tmp_path / "plan.json"
    monday = tmp_path / "monday.json"
    drk = tmp_path / "drk.json"
    config = tmp_path / "config.json"
    _write(canonical, {"source": {"file_name": "synthetic.pdf"}, "patient": {}, "field_quality": {}, "warnings": []})
    _write(plan, {"outcome": "blocked_missing_threshold", "monday_duplicate_check": {"status": "skipped_missing_identity"}})
    _write(monday, {"item_name": None, "column_values": {}, "blocked": True, "blockers": ["missing_patient_name"]})
    _write(drk, {"ready_for_fill": False, "blockers": ["missing_required:first_name"], "payload": {}})
    _write(config, {"columns": {}})

    _, body = render_review_email(
        review_id="review_abc123_xyz987",
        token="abcdefghijklmnop",
        canonical_path=canonical,
        intake_plan_path=plan,
        monday_preview_path=monday,
        drk_draft_path=drk,
        write_config_path=config,
        approval_allowed=False,
    )

    assert "cannot be approved" in body
    assert "CONFIRMED review_" not in body
