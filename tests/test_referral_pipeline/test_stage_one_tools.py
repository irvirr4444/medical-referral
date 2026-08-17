from __future__ import annotations

import json

from referral_pipeline.stage_one.email_preview import render_stage_one_email_preview
from referral_pipeline.stage_one.preflight import run_stage_one_preflight


def test_preflight_requires_an_internal_reviewer_and_loads_synthetic_hashes(
    tmp_path, monkeypatch
) -> None:
    manifest = tmp_path / "dataset.json"
    manifest.write_text(
        json.dumps({"synthetic_only": True, "cases": [{"sha256": "a" * 64}]}),
        encoding="utf-8",
    )
    monkeypatch.setenv("SYNTHETIC_DATASET_MANIFEST", str(manifest))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("OUTLOOK_TENANT_ID", "tenant")
    monkeypatch.setenv("OUTLOOK_CLIENT_ID", "client")
    monkeypatch.setenv("OUTLOOK_CLIENT_SECRET", "secret")
    monkeypatch.setenv("OUTLOOK_MAILBOX", "inbox@example.test")
    monkeypatch.setenv("WORKFLOW_DATABASE_BACKEND", "sqlite")
    monkeypatch.setenv("REFERRAL_REVIEW_STORE", "sqlite")
    monkeypatch.setenv("WORKFLOW_SQLITE_PATH", str(tmp_path / "workflow.sqlite"))
    monkeypatch.setenv("INTAKE_DATA_ROOT", str(tmp_path))
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    monkeypatch.setenv("REVIEW_RECIPIENT_EMAIL", "")

    missing = run_stage_one_preflight()
    assert missing["ready"] is False
    assert next(item for item in missing["checks"] if item["name"] == "internal_reviewer")["status"] == "error"

    monkeypatch.setenv("REVIEW_RECIPIENT_EMAIL", "intake@example.test")
    ready = run_stage_one_preflight()
    assert ready["ready"] is True
    assert next(item for item in ready["checks"] if item["name"] == "synthetic_allowlist")["status"] == "ok"
    assert next(item for item in ready["checks"] if item["name"] == "case_manager_roster")["status"] == "ok"
    assert next(item for item in ready["checks"] if item["name"] == "local_schema")["status"] == "ok"


def test_email_preview_renders_both_messages_without_sending(tmp_path) -> None:
    artifact = tmp_path / "artifact"
    artifact.mkdir()
    canonical = artifact / "canonical-referral.json"
    plan = artifact / "intake-plan.json"
    monday = artifact / "master-sheet-preview.json"
    drk = artifact / "drk-create-draft.json"
    config = artifact / "config.json"
    canonical.write_text(
        json.dumps(
            {
                "patient": {"name": {"full": "TEST Patient"}},
                "clinical": {},
                "field_quality": {},
                "insurances": [],
                "requested_services": [],
            }
        ),
        encoding="utf-8",
    )
    plan.write_text(
        json.dumps(
            {
                "validation": {
                    "threshold_missing": [],
                    "supporting_missing": [],
                    "field_labels": {},
                },
                "monday_duplicate_check": {},
            }
        ),
        encoding="utf-8",
    )
    monday.write_text("{}", encoding="utf-8")
    drk.write_text("{}", encoding="utf-8")
    config.write_text("{}", encoding="utf-8")
    (artifact / "manifest.json").write_text(
        json.dumps(
            {
                "canonical_referral_path": str(canonical),
                "plan_path": str(plan),
                "preview_path": str(monday),
                "drk_draft_path": str(drk),
                "source_sender": "partner@example.test",
                "source_message_id": "message-1",
            }
        ),
        encoding="utf-8",
    )

    result = render_stage_one_email_preview(
        tmp_path,
        reviewer="intake@example.test",
        write_config_path=config,
    )

    assert result["messages_sent"] is False
    assert result["writes_performed"] is False
    assert result["internal_review"]["recipient"] == "intake@example.test"
    assert result["partner_acknowledgement"]["recipient"] == "partner@example.test"
    assert "Referral Follow-up: TEST Patient" == result["internal_review"]["subject"]
