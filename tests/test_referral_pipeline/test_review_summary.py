from __future__ import annotations

import json

from referral_pipeline.review.summary import NOT_DOCUMENTED, NO_KNOWN_ALLERGIES, render_review_email


def _write(path, value) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def _base_paths(tmp_path):
    canonical = tmp_path / "canonical.json"
    monday = tmp_path / "monday.json"
    plan = tmp_path / "plan.json"
    drk = tmp_path / "drk.json"
    config = tmp_path / "config.json"
    _write(plan, {"outcome": "ready_for_human_approval", "review_reasons": [], "monday_duplicate_check": {"status": "no_candidates_found", "candidates": []}})
    _write(drk, {"ready_for_fill": False, "blockers": [], "unresolved_fields": [], "payload": {}})
    _write(config, {"columns": {}})
    return canonical, monday, plan, drk, config


def test_summary_renders_readable_html_and_plain_text(tmp_path) -> None:
    canonical, monday, plan, drk, config = _base_paths(tmp_path)
    _write(
        canonical,
        {
            "source": {"file_name": "synthetic.pdf"},
            "patient": {
                "name": {"first": "JAMIE", "last": "TESTER", "full": "TESTER, JAMIE"},
                "date_of_birth": "1958-01-15",
                "phones": [{"number": "555-0100"}],
                "address": {"line_1": "1 TEST WAY", "city": "FRESNO", "state": "CA", "postal_code": "93701"},
            },
            "referral_source": {"organization": {"name": "Synthetic Home Health"}},
            "home_health_or_hospice": {"organization": {"name": "Synthetic Home Health"}},
            "clinical": {
                "summary": "Synthetic wound referral",
                "diagnoses": [
                    {"code": "L89.154", "description": "PRESSURE ULCER"},
                    {"code": "E11.9", "description": "TYPE 2 DIABETES"},
                ],
                "medications": [
                    {"name": "acetaminophen", "strength": "325 mg", "directions": "take two tabs Q 6 hrs prn"},
                    {"name": "Eliquis", "strength": "5 mg", "directions": "Take one tab by mouth twice daily"},
                ],
                "allergies": [],
                "allergies_section_present": True,
                "no_known_allergies_explicit": False,
                "notes": ["No signed order found"],
            },
            "insurances": [{"payer_name": "Synthetic Payer", "policy_number": "TEST-1"}],
            "requested_services": [{"service": "Wound Care"}],
            "field_quality": {"allergies": {"status": "missing"}},
            "warnings": ["Allergy section empty"],
        },
    )
    _write(monday, {"item_name": "Jamie Tester", "column_values": {}, "mapping_notes": [], "blocked": False, "blockers": []})

    email = render_review_email(
        review_id="review_abc123_xyz987",
        token="abcdefghijklmnop",
        canonical_path=canonical,
        intake_plan_path=plan,
        monday_preview_path=monday,
        drk_draft_path=drk,
        write_config_path=config,
    )

    assert email.content_type == "HTML"
    assert "Jamie Tester" in email.subject or "review_abc123_xyz987" in email.subject
    assert "Referral Review: Jamie Tester" in email.html_body
    assert "Needs attention" in email.html_body
    assert "Allergies" in email.html_body
    assert NOT_DOCUMENTED in email.html_body
    assert "Diagnoses (2)" in email.html_body
    assert "Medications (2)" in email.html_body
    assert "<strong>L89.154</strong>" in email.html_body
    assert "acetaminophen" in email.html_body
    assert "January 15, 1958" in email.html_body
    assert "1 Test Way, Fresno, CA, 93701" in email.html_body
    assert "CONFIRMED review_abc123_xyz987 abcdefghijklmnop" in email.html_body
    assert "CONFIRMED review_abc123_xyz987 abcdefghijklmnop" in email.text_body
    assert "create this patient&#39;s data in Monday" in email.html_body
    assert "prepare the audited DRK handoff" in email.text_body
    assert "correct a field" in email.text_body
    assert "Duplicate found in Monday" not in email.text_body
    assert "Clinical summary" in email.text_body
    assert "Document observations" not in email.text_body
    assert "No signed order found" not in email.html_body
    assert "Allergy section empty" not in email.html_body
    assert "MONDAY.COM PROPOSED WRITE" not in email.text_body
    assert "<script" not in email.html_body.lower()


def test_html_escapes_untrusted_values(tmp_path) -> None:
    canonical, monday, plan, drk, config = _base_paths(tmp_path)
    _write(
        canonical,
        {
            "patient": {"name": {"full": "Jane <script>alert(1)</script> Doe"}, "date_of_birth": "2000-01-02", "phones": [], "address": {}},
            "referral_source": {"organization": {"name": "Clinic & Co"}},
            "home_health_or_hospice": {"organization": {"name": "HH"}},
            "clinical": {"summary": "A & B", "diagnoses": [], "medications": [], "allergies": [], "notes": []},
            "insurances": [],
            "requested_services": [{"service": "Wound Care"}],
            "field_quality": {},
            "warnings": [],
        },
    )
    _write(monday, {"blocked": False, "blockers": []})

    email = render_review_email(
        review_id="review_abc123_xyz987",
        token="abcdefghijklmnop",
        canonical_path=canonical,
        intake_plan_path=plan,
        monday_preview_path=monday,
        drk_draft_path=drk,
        write_config_path=config,
    )

    assert "<script>alert(1)</script>" not in email.html_body
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in email.html_body
    assert "Clinic &amp; Co" in email.html_body


def test_explicit_nka_is_distinguished_from_missing_allergies(tmp_path) -> None:
    canonical, monday, plan, drk, config = _base_paths(tmp_path)
    _write(
        canonical,
        {
            "patient": {"name": {"full": "Jane Doe"}, "date_of_birth": "2000-01-02", "phones": [{"number": "1"}], "address": {"line_1": "1 Main"}},
            "referral_source": {"organization": {"name": "Clinic"}},
            "home_health_or_hospice": {"organization": {"name": "HH"}},
            "clinical": {
                "summary": "Summary",
                "diagnoses": [],
                "medications": [],
                "allergies": [],
                "no_known_allergies_explicit": True,
                "notes": [],
            },
            "insurances": [{"payer_name": "Medicare", "policy_number": "1"}],
            "requested_services": [{"service": "Wound Care"}],
            "field_quality": {},
            "warnings": [],
        },
    )
    _write(monday, {"blocked": False, "blockers": []})

    email = render_review_email(
        review_id="review_abc123_xyz987",
        token="abcdefghijklmnop",
        canonical_path=canonical,
        intake_plan_path=plan,
        monday_preview_path=monday,
        drk_draft_path=drk,
        write_config_path=config,
    )

    assert NO_KNOWN_ALLERGIES in email.html_body
    assert "no NKA/NKDA statement found" not in email.html_body


def test_blocked_summary_does_not_include_approval_command(tmp_path) -> None:
    canonical, monday, plan, drk, config = _base_paths(tmp_path)
    _write(canonical, {"source": {"file_name": "synthetic.pdf"}, "patient": {}, "field_quality": {}, "warnings": [], "clinical": {}, "insurances": [], "requested_services": []})
    _write(plan, {"outcome": "blocked_missing_threshold", "monday_duplicate_check": {"status": "skipped_missing_identity"}})
    _write(monday, {"item_name": None, "column_values": {}, "blocked": True, "blockers": ["missing_patient_name"]})
    _write(drk, {"ready_for_fill": False, "blockers": ["missing_required:first_name"], "payload": {}})

    email = render_review_email(
        review_id="review_abc123_xyz987",
        token="abcdefghijklmnop",
        canonical_path=canonical,
        intake_plan_path=plan,
        monday_preview_path=monday,
        drk_draft_path=drk,
        write_config_path=config,
        approval_allowed=False,
    )

    assert "cannot be confirmed yet" in email.text_body
    assert "Reply with any additional details or field corrections" in email.text_body
    assert "CONFIRMED review_" not in email.text_body
    assert "CONFIRMED review_" not in email.html_body


def test_duplicate_warning_lists_four_matching_monday_fields(tmp_path) -> None:
    canonical, monday, plan, drk, config = _base_paths(tmp_path)
    _write(
        canonical,
        {
            "patient": {
                "name": {"full": "Jane Doe"},
                "date_of_birth": "1980-01-02",
                "phones": [{"number": "555-555-0100"}],
                "address": {"line_1": "100 Example Street", "city": "Tampa", "state": "FL", "postal_code": "33602"},
            },
            "clinical": {},
            "field_quality": {},
            "insurances": [],
            "requested_services": [],
        },
    )
    _write(
        plan,
        {
            "outcome": "manual_review_required",
            "monday_duplicate_check": {
                "status": "duplicate_found",
                "candidates": [
                    {
                        "fields": {
                            "name": "Doe, Jane",
                            "dob": "Jan 2, 1980",
                            "patient_phone": "(555) 555-0100",
                            "patient_address": "100 Example Street, Tampa, FL 33602",
                        }
                    }
                ],
            },
        },
    )
    _write(monday, {"blocked": True, "blockers": ["duplicate_check_is_duplicate_found"]})

    email = render_review_email(
        review_id="review_abc123_xyz987",
        token="abcdefghijklmnop",
        canonical_path=canonical,
        intake_plan_path=plan,
        monday_preview_path=monday,
        drk_draft_path=drk,
        write_config_path=config,
        approval_allowed=False,
    )

    assert "Duplicate patient in Monday" in email.text_body
    assert "Name: Doe, Jane" in email.text_body
    assert "DOB: January 2, 1980" in email.text_body
    assert "Phone: (555) 555-0100" in email.text_body
    assert "Address: 100 Example Street, Tampa, FL 33602" in email.text_body
    assert "Duplicate found in Monday" in email.html_body
    assert "Do not create another patient" in email.text_body
    assert "CONFIRMED review_" not in email.text_body
