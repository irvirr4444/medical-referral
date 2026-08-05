from __future__ import annotations

import json
from pathlib import Path

from referral_pipeline import cli as intake


def _write_completed_run(argv: list[str], *, blocked: bool = False, created_item_id: str | None = None) -> None:
    output_dir = Path(argv[argv.index("--output-dir") + 1])
    artifact_dir = output_dir / "abc123"
    artifact_dir.mkdir(parents=True)
    preview_path = artifact_dir / "master-sheet-preview.json"
    preview_path.write_text(
        json.dumps(
            {
                "board_id": 1,
                "group_id": "topics",
                "operation": "create_item",
                "item_name": "TEST Jamie Tester",
                "column_values": {},
                "post_create_actions": [],
                "blocked": blocked,
                "blockers": ["blocked_for_test"] if blocked else [],
                "mode": "apply" if created_item_id else "dry-run",
            }
        ),
        encoding="utf-8",
    )
    (output_dir / "run-summary.json").write_text(
        json.dumps(
            [
                {
                    "filename": "synthetic-complete-referral.pdf",
                    "status": "completed",
                    "attachment_sha256": "abc123",
                    "preview_path": str(preview_path),
                    "master_sheet_blocked": blocked,
                    "master_sheet_blockers": ["blocked_for_test"] if blocked else [],
                    "created_item_id": created_item_id,
                }
            ]
        ),
        encoding="utf-8",
    )


def test_outlook_defaults_to_one_message_and_dry_run(tmp_path, monkeypatch, capsys) -> None:
    delegated: list[str] = []

    def fake_run(argv: list[str]) -> int:
        delegated.extend(argv)
        _write_completed_run(argv)
        return 0

    monkeypatch.setattr(intake, "run_inbound_main", fake_run)

    assert intake.main(["outlook", "--output-root", str(tmp_path)]) == 0

    assert delegated[delegated.index("--max-messages") + 1] == "1"
    assert delegated[delegated.index("--input-mode") + 1] == "image"
    assert delegated[delegated.index("--monday-mode") + 1] == "live-readonly"
    assert delegated[delegated.index("--agency-mode") + 1] == "live-readonly"
    assert delegated[delegated.index("--master-sheet-mode") + 1] == "dry-run"
    assert "--confirm-master-sheet-write" not in delegated
    assert "--verbose" in delegated

    latest = json.loads((tmp_path / "latest.json").read_text(encoding="utf-8"))
    assert latest["status"] == "ready"
    assert latest["item_name"] == "TEST Jamie Tester"
    assert "run_pipeline.py apply --confirm-master-sheet-write" in capsys.readouterr().out


def test_direct_apply_requires_explicit_confirmation(tmp_path, monkeypatch, capsys) -> None:
    called = False

    def fake_run(_argv: list[str]) -> int:
        nonlocal called
        called = True
        return 0

    monkeypatch.setattr(intake, "run_inbound_main", fake_run)

    assert intake.main(["outlook", "--apply", "--output-root", str(tmp_path)]) == 2
    assert not called
    assert "--apply requires --confirm-master-sheet-write" in capsys.readouterr().err


def test_outlook_quiet_mode_suppresses_low_level_verbose_flag(tmp_path, monkeypatch) -> None:
    delegated: list[str] = []

    def fake_run(argv: list[str]) -> int:
        delegated.extend(argv)
        _write_completed_run(argv)
        return 0

    monkeypatch.setattr(intake, "run_inbound_main", fake_run)

    assert intake.main(["outlook", "--quiet", "--output-root", str(tmp_path)]) == 0
    assert "--verbose" not in delegated


def test_outlook_can_delegate_review_email(tmp_path, monkeypatch) -> None:
    delegated: list[str] = []

    def fake_run(argv: list[str]) -> int:
        delegated.extend(argv)
        _write_completed_run(argv)
        return 0

    monkeypatch.setattr(intake, "run_inbound_main", fake_run)

    assert intake.main(["outlook", "--send-review", "--review-recipient", "reviewer@example.test", "--output-root", str(tmp_path)]) == 0

    assert "--send-review" in delegated
    assert delegated[delegated.index("--review-recipient") + 1] == "reviewer@example.test"


def test_review_email_cannot_be_combined_with_immediate_write(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(intake, "run_inbound_main", lambda _argv: (_ for _ in ()).throw(AssertionError()))

    assert intake.main(["outlook", "--send-review", "--apply", "--confirm-master-sheet-write", "--output-root", str(tmp_path)]) == 2
    assert "cannot be combined" in capsys.readouterr().err


def test_apply_uses_exact_latest_preview_and_marks_it_applied(tmp_path, monkeypatch, capsys) -> None:
    run_dir = tmp_path / "20260803-120000" / "abc123"
    run_dir.mkdir(parents=True)
    preview_path = run_dir / "master-sheet-preview.json"
    preview_path.write_text(
        json.dumps(
            {
                "board_id": 1,
                "group_id": "topics",
                "operation": "create_item",
                "item_name": "TEST Jamie Tester",
                "column_values": {"dob": {"date": "1958-01-15"}},
                "post_create_actions": [],
                "blocked": False,
                "blockers": [],
                "mode": "dry-run",
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "latest.json").write_text(
        json.dumps(
            {
                "version": 1,
                "status": "ready",
                "item_name": "TEST Jamie Tester",
                "preview_path": str(preview_path),
            }
        ),
        encoding="utf-8",
    )
    applied: list[dict] = []

    def fake_apply(preview: dict) -> dict:
        applied.append(preview)
        return {"item": {"id": "12345"}, "update": None}

    monkeypatch.setattr(intake, "apply_master_sheet_create", fake_apply)

    assert intake.main(["apply", "--output-root", str(tmp_path), "--confirm-master-sheet-write"]) == 0

    assert applied[0]["item_name"] == "TEST Jamie Tester"
    assert applied[0]["mode"] == "apply"
    latest = json.loads((tmp_path / "latest.json").read_text(encoding="utf-8"))
    assert latest["status"] == "applied"
    assert latest["created_item_id"] == "12345"
    assert (run_dir / "master-sheet-apply-result.json").is_file()
    assert '"created_item_id": "12345"' in capsys.readouterr().out


def test_apply_refuses_a_preview_with_an_existing_result(tmp_path, monkeypatch, capsys) -> None:
    preview_path = tmp_path / "master-sheet-preview.json"
    preview_path.write_text(
        json.dumps(
            {
                "operation": "create_item",
                "item_name": "TEST Jamie Tester",
                "blocked": False,
                "blockers": [],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "master-sheet-apply-result.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(intake, "apply_master_sheet_create", lambda _preview: (_ for _ in ()).throw(AssertionError()))

    assert (
        intake.main(
            [
                "apply",
                "--preview",
                str(preview_path),
                "--confirm-master-sheet-write",
            ]
        )
        == 2
    )
    assert "already has an apply result" in capsys.readouterr().err


def test_review_send_reuses_existing_manifest(tmp_path, monkeypatch, capsys) -> None:
    run_dir = tmp_path / "20260804-120000"
    artifact_dir = run_dir / "abc123"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "manifest.json").write_text(json.dumps({"preview_path": "preview.json"}), encoding="utf-8")
    sent = []
    monkeypatch.setattr(intake.OutlookGraphConfig, "from_environment", lambda: object())
    monkeypatch.setattr(intake, "OutlookGraphClient", lambda _config: object())
    monkeypatch.setenv("REVIEW_RECIPIENT_EMAIL", "reviewer@example.test")
    monkeypatch.setattr(
        intake,
        "create_and_send_review",
        lambda manifest, **kwargs: sent.append((manifest, kwargs)) or {"review_id": "review_test"},
    )

    assert intake.main(["review-send", "--run", str(run_dir)]) == 0

    assert sent[0][1]["recipient"] == "reviewer@example.test"
    assert sent[0][1]["state_db"] == tmp_path / "state.sqlite"
    assert "review_test" in capsys.readouterr().out
