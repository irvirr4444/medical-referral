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


def test_preflight_requires_only_selected_optional_capabilities(tmp_path, monkeypatch) -> None:
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
    monkeypatch.setenv("REVIEW_RECIPIENT_EMAIL", "intake@example.test")
    monkeypatch.setenv("WORKFLOW_DATABASE_BACKEND", "sqlite")
    monkeypatch.setenv("REFERRAL_REVIEW_STORE", "sqlite")
    monkeypatch.setenv("WORKFLOW_SQLITE_PATH", str(tmp_path / "workflow.sqlite"))
    monkeypatch.setenv("INTAKE_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "")
    monkeypatch.setenv("EMR_URL", "")
    monkeypatch.setenv("EMR_USERNAME", "")
    monkeypatch.setenv("EMR_PASSWORD", "")

    sqlite_run = run_stage_one_preflight(require_supabase=False, require_drk=False)
    assert sqlite_run["ready"] is True
    assert next(item for item in sqlite_run["checks"] if item["name"] == "supabase")["status"] == "warning"
    assert next(item for item in sqlite_run["checks"] if item["name"] == "drk_read")["status"] == "warning"

    supabase_run = run_stage_one_preflight(require_supabase=True)
    assert supabase_run["ready"] is False
    assert next(item for item in supabase_run["checks"] if item["name"] == "supabase")["status"] == "error"
    assert "Remediation:" in next(
        item for item in supabase_run["checks"] if item["name"] == "supabase"
    )["detail"]

    drk_run = run_stage_one_preflight(require_supabase=False, require_drk=True)
    assert drk_run["ready"] is False
    assert next(item for item in drk_run["checks"] if item["name"] == "drk_read")["status"] == "error"


def test_preflight_can_run_outlook_and_supabase_live_without_monday_or_drk(
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
    monkeypatch.setenv("REVIEW_RECIPIENT_EMAIL", "intake@example.test")
    monkeypatch.setenv("WORKFLOW_DATABASE_BACKEND", "supabase")
    monkeypatch.setenv("REFERRAL_REVIEW_STORE", "sqlite")
    monkeypatch.setenv("WORKFLOW_SQLITE_PATH", str(tmp_path / "workflow.sqlite"))
    monkeypatch.setenv("INTAKE_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role")
    monkeypatch.setenv("MONDAY_DOT_COM_API_KEY", "monday-key")
    monkeypatch.setenv("EMR_URL", "https://emr.example.test")
    monkeypatch.setenv("EMR_USERNAME", "user")
    monkeypatch.setenv("EMR_PASSWORD", "pass")
    monkeypatch.setattr(
        "referral_pipeline.stage_one.preflight._check_outlook",
        lambda: "Mailbox read succeeded",
    )
    monkeypatch.setattr(
        "referral_pipeline.stage_one.preflight._check_supabase",
        lambda: "Required Stage 1-3 Supabase tables are readable",
    )

    result = run_stage_one_preflight(
        require_supabase=True,
        live_outlook=True,
        live_supabase=True,
    )
    names = [item["name"] for item in result["checks"]]
    assert result["ready"] is True
    assert "outlook_live" in names
    assert "supabase_schema" in names
    assert "monday_live" not in names
    assert "drk_live" not in names


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


class _FakeDrkDriver:
    current_url = "https://emr.example.test/Dashboard"

    def __init__(self) -> None:
        self.quit_called = False

    def quit(self) -> None:
        self.quit_called = True


def test_drk_preflight_quits_chrome_before_deleting_the_temp_profile(
    tmp_path, monkeypatch
) -> None:
    from referral_pipeline.stage_one.preflight import _check_drk

    events: list[str] = []
    driver = _FakeDrkDriver()
    profile = tmp_path / "drk-preflight"
    profile.mkdir()

    class TrackingTempDir:
        def __init__(self, *args, **kwargs):
            self.name = str(profile)

        def cleanup(self) -> None:
            events.append("cleanup")
            assert driver.quit_called is True

    monkeypatch.setenv("EMR_USERNAME", "user")
    monkeypatch.setenv("EMR_PASSWORD", "pass")
    monkeypatch.setenv("EMR_URL", "https://emr.example.test")
    monkeypatch.setattr("tempfile.TemporaryDirectory", TrackingTempDir)
    monkeypatch.setattr("drk_emr.common.browser.make_driver", lambda _path: driver)
    monkeypatch.setattr("drk_emr.common.browser.login", lambda *_args, **_kwargs: None)

    assert "dashboard is reachable" in _check_drk()
    assert events == ["cleanup"]
    assert driver.quit_called is True


def test_drk_preflight_ignores_windows_profile_lock_after_successful_login(
    tmp_path, monkeypatch
) -> None:
    from referral_pipeline.stage_one.preflight import _check_drk

    driver = _FakeDrkDriver()
    profile = tmp_path / "drk-preflight"
    profile.mkdir()

    class LockedTempDir:
        def __init__(self, *args, **kwargs):
            self.name = str(profile)

        def cleanup(self) -> None:
            raise PermissionError(
                32,
                "The process cannot access the file because it is being used by another process",
                str(profile / "Default" / "Cache" / "No_Vary_Search" / "journal.baj"),
            )

    monkeypatch.setenv("EMR_USERNAME", "user")
    monkeypatch.setenv("EMR_PASSWORD", "pass")
    monkeypatch.setenv("EMR_URL", "https://emr.example.test")
    monkeypatch.setattr("tempfile.TemporaryDirectory", LockedTempDir)
    monkeypatch.setattr("drk_emr.common.browser.make_driver", lambda _path: driver)
    monkeypatch.setattr("drk_emr.common.browser.login", lambda *_args, **_kwargs: None)

    assert "dashboard is reachable" in _check_drk()
    assert driver.quit_called is True
