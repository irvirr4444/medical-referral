from __future__ import annotations

import master_sheet_writer
from master_sheet_writer import MasterSheetWriteConfig, apply_master_sheet_create, build_master_sheet_create_preview


def _config() -> MasterSheetWriteConfig:
    return MasterSheetWriteConfig(
        board_id=1,
        group_id="working",
        stage_label="In intake",
        phone_country_code="US",
        patient_dob_column="dob",
        patient_phone_column="phone",
        stage_column="stage",
        agency_relation_column="agency",
        accounts_board_id="2",
        write_stage=True,
    )


def _plan(
    *,
    outcome: str = "ready_for_human_approval",
    duplicate_status: str = "no_candidates_found",
    duplicate_mode: str = "live-readonly",
) -> dict:
    return {
        "outcome": outcome,
        "monday_duplicate_check": {"mode": duplicate_mode, "status": duplicate_status},
        "referral": {
            "patient_name": "Example, Patient",
            "patient_dob": "01/02/1980",
            "patient_phone": "555-555-0100",
            "patient_address": "1 Example Street",
            "referring_facility": "Example Home Health",
            "referral_date": "01/03/1980",
            "insurance_provider": "Example Insurance",
            "diagnosis_text": "Chronic wound",
        },
    }


def test_preview_maps_only_verified_master_sheet_fields() -> None:
    preview = build_master_sheet_create_preview(_plan(), config=_config())

    assert not preview["blocked"]
    assert preview["item_name"] == "Example, Patient"
    assert preview["column_values"] == {
        "stage": {"label": "In intake"},
        "dob": {"date": "1980-01-02"},
        "phone": {"phone": "+15555550100", "countryShortName": "US"},
    }
    assert {note["field"] for note in preview["mapping_notes"]} == {
        "patient_address",
        "referring_facility",
        "referral_date",
        "insurance",
        "clinical_information",
    }


def test_preview_maps_intake_columns_with_a_confirmed_inbound_timestamp() -> None:
    config = MasterSheetWriteConfig(
        **{
            **_config().__dict__,
            "referral_received_column": "received",
            "agency_phone_column": "agency_phone",
            "comments_column": "comments",
            "write_referral_received": True,
        }
    )
    plan = _plan()
    plan["referral"]["referring_phone"] = "555-555-0199"
    plan["source"] = {"received_at": "2026-07-30T15:00:00+00:00"}

    preview = build_master_sheet_create_preview(plan, config=config)

    assert preview["column_values"]["received"] == {"date": "2026-07-30", "time": "15:00:00"}
    assert preview["column_values"]["agency_phone"] == "555-555-0199"
    assert "Patient address: 1 Example Street" in preview["column_values"]["comments"]


def test_preview_leaves_automation_and_restricted_columns_unwritten() -> None:
    config = MasterSheetWriteConfig(
        **{
            **_config().__dict__,
            "comments_column": "comments",
            "referral_received_column": "received",
            "write_stage": False,
            "write_referral_received": False,
        }
    )
    plan = _plan()
    plan["source"] = {"received_at": "2026-07-30T15:00:00+00:00"}

    preview = build_master_sheet_create_preview(plan, config=config)

    assert "stage" not in preview["column_values"]
    assert "received" not in preview["column_values"]
    assert "Inbox received at: 2026-07-30T15:00:00+00:00" in preview["column_values"]["comments"]
    reasons = {note["reason"] for note in preview["mapping_notes"]}
    assert "managed_by_existing_monday_automation" in reasons
    assert "stored_in_comments_and_item_update_column_write_not_enabled" in reasons


def test_duplicate_or_nonapproved_plan_is_blocked() -> None:
    duplicate_preview = build_master_sheet_create_preview(_plan(duplicate_status="duplicate_found"), config=_config())
    review_preview = build_master_sheet_create_preview(_plan(outcome="manual_review_required"), config=_config())

    assert duplicate_preview["blocked"]
    assert "duplicate_check_is_duplicate_found" in duplicate_preview["blockers"]
    assert review_preview["blocked"]
    assert "plan_outcome_is_manual_review_required" in review_preview["blockers"]


def test_deliberately_disabled_duplicate_check_does_not_block_test_review() -> None:
    preview = build_master_sheet_create_preview(
        _plan(duplicate_status="not_checked", duplicate_mode="disabled"),
        config=_config(),
    )

    assert not preview["blocked"]
    assert "duplicate_check_is_not_checked" not in preview["blockers"]


def test_preview_links_one_exact_agency_and_preserves_context_in_update() -> None:
    preview = build_master_sheet_create_preview(
        _plan(),
        config=_config(),
        agency_matches=[{"id": "456", "name": "Example Home Health"}],
    )

    assert preview["column_values"]["agency"] == {"item_ids": ["456"]}
    assert preview["post_create_actions"][0]["type"] == "create_update"
    assert "Clinical information" in preview["post_create_actions"][0]["body"]
    assert len(preview["post_create_actions"]) == 1


def test_partial_referral_is_blocked_even_with_configured_case_manager() -> None:
    plan = _plan(outcome="manual_review_required")
    plan["review_reasons"] = ["missing_supporting_fields"]
    plan["proposed_actions"] = [{"type": "route_partial_referral_to_case_manager"}]
    configured = MasterSheetWriteConfig(**{**_config().__dict__, "case_manager_column": "owner", "sent_to_case_manager_column": "sent", "time_sent_to_case_manager_column": "sent_at", "default_case_manager_id": "99"})

    preview = build_master_sheet_create_preview(plan, config=configured)

    assert preview["blocked"]
    assert "plan_outcome_is_manual_review_required" in preview["blockers"]
    assert preview["column_values"]["owner"] == {"personsAndTeams": [{"id": 99, "kind": "person"}]}
    assert preview["column_values"]["sent"] == {"label": "Yes"}
    assert "sent_at" in preview["column_values"]


def test_apply_creates_item_then_update(monkeypatch) -> None:
    preview = build_master_sheet_create_preview(_plan(), config=_config())
    calls: list[str] = []
    monkeypatch.setattr(master_sheet_writer, "create_master_sheet_item", lambda _preview: calls.append("item") or {"id": "1"})
    monkeypatch.setattr(master_sheet_writer, "_create_item_update", lambda **_kwargs: calls.append("update") or {"id": "2"})

    result = apply_master_sheet_create(preview)

    assert calls == ["item", "update"]
    assert result["applied_actions"] == [{"type": "create_update", "update_id": "2"}]


def test_apply_persists_item_id_before_post_create_update(monkeypatch) -> None:
    preview = build_master_sheet_create_preview(_plan(), config=_config())
    calls: list[str] = []
    monkeypatch.setattr(
        master_sheet_writer,
        "create_master_sheet_item",
        lambda _preview: calls.append("item") or {"id": "1"},
    )
    monkeypatch.setattr(
        master_sheet_writer,
        "_create_item_update",
        lambda **_kwargs: calls.append("update") or {"id": "2"},
    )

    apply_master_sheet_create(
        preview,
        on_item_created=lambda item: calls.append(f"persist:{item['id']}"),
    )

    assert calls == ["item", "persist:1", "update"]
