from __future__ import annotations

import json

from Outlook.review_mail import ReviewReply
from referral_pipeline.review.store import ReviewStore
from referral_pipeline.review.workflow import ApprovalProcessor, artifact_digest


class FakeMailbox:
    def __init__(self, replies):
        self.replies = replies

    def list_replies(self, *, max_messages: int = 25):
        return self.replies[:max_messages]


def _write(path, value) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def test_confirmed_review_applies_monday_once_then_creates_drk_handoff(tmp_path, monkeypatch) -> None:
    canonical = tmp_path / "canonical-referral.json"
    plan = tmp_path / "intake-plan.json"
    preview = tmp_path / "master-sheet-preview.json"
    drk = tmp_path / "drk-create-draft.json"
    _write(canonical, {"referral_id": "ref_test"})
    _write(plan, {"outcome": "ready_for_human_approval"})
    _write(preview, {"operation": "create_item", "item_name": "TEST Jamie Tester", "blocked": False})
    _write(drk, {"ready_for_fill": False, "payload": {}})
    paths = [canonical, plan, preview, drk]
    state_db = tmp_path / "state.sqlite"
    store = ReviewStore(state_db)
    store.add(
        review_id="review_abc123_xyz987",
        token="abcdefghijklmnop",
        recipient="reviewer@example.test",
        artifact_digest=artifact_digest(paths),
        canonical_path=str(canonical),
        intake_plan_path=str(plan),
        monday_preview_path=str(preview),
        drk_draft_path=str(drk),
        source_message_id="source-message",
    )
    mailbox = FakeMailbox(
        [
            ReviewReply(
                message_id="reply-1",
                sender="reviewer@example.test",
                subject="Re: review",
                received_at=None,
                conversation_id=None,
                text="CONFIRMED review_abc123_xyz987 abcdefghijklmnop",
            )
        ]
    )
    calls = []
    monkeypatch.setattr(
        "master_sheet_writer.apply_master_sheet_create",
        lambda value: calls.append(value) or {"item": {"id": "monday-123"}, "applied_actions": []},
    )

    first = ApprovalProcessor(state_db=state_db, mailbox=mailbox).poll(execute=True)
    second = ApprovalProcessor(state_db=state_db, mailbox=mailbox).poll(execute=True)

    assert first["accepted_confirmations"] == ["review_abc123_xyz987"]
    assert first["executed"][0]["status"] == "monday_applied_drk_pending"
    assert len(calls) == 1
    assert second["executed"] == []
    assert json.loads((tmp_path / "drk-handoff.json").read_text(encoding="utf-8"))["monday_item_id"] == "monday-123"
    assert ReviewStore(state_db).get("review_abc123_xyz987").status == "monday_applied_drk_pending"


class RecordingMailbox:
    def __init__(self):
        self.sent = []

    def send_review(self, *, recipient: str, subject: str, text_body: str | None = None, html_body: str | None = None, content_type: str = "HTML", body: str | None = None) -> None:
        self.sent.append(
            {
                "recipient": recipient,
                "subject": subject,
                "text_body": text_body,
                "html_body": html_body,
                "content_type": content_type,
                "body": body,
            }
        )

    def list_replies(self, *, max_messages: int = 25):
        return []


def test_create_and_send_review_reuses_active_request(tmp_path) -> None:
    from referral_pipeline.review.workflow import create_and_send_review

    canonical = tmp_path / "canonical-referral.json"
    plan = tmp_path / "intake-plan.json"
    preview = tmp_path / "master-sheet-preview.json"
    drk = tmp_path / "drk-create-draft.json"
    config = tmp_path / "config.json"
    _write(canonical, {"patient": {"name": {"full": "Jane"}}, "source": {"file_name": "a.pdf"}, "clinical": {}, "insurances": [], "requested_services": [], "warnings": [], "field_quality": {}})
    _write(plan, {"outcome": "ready_for_human_approval", "review_reasons": [], "monday_duplicate_check": {"status": "no_candidates_found", "candidates": []}})
    _write(preview, {"item_name": "Jane", "blocked": False, "blockers": [], "column_values": {}})
    _write(drk, {"ready_for_fill": False, "payload": {}, "blockers": []})
    _write(config, {"columns": {}})
    manifest = {
        "canonical_referral_path": str(canonical),
        "plan_path": str(plan),
        "preview_path": str(preview),
        "drk_draft_path": str(drk),
        "source_message_id": "source-message",
    }
    mailbox = RecordingMailbox()
    state_db = tmp_path / "state.sqlite"

    first = create_and_send_review(
        manifest,
        recipient="reviewer@example.test",
        write_config_path=config,
        state_db=state_db,
        mailbox=mailbox,
    )
    second = create_and_send_review(
        manifest,
        recipient="reviewer@example.test",
        write_config_path=config,
        state_db=state_db,
        mailbox=mailbox,
    )

    assert first["review_id"] == second["review_id"]
    assert second["review_reused"] is True
    assert first["review_content_type"] == "HTML"
    assert len(mailbox.sent) == 2
    assert mailbox.sent[0]["recipient"] == "reviewer@example.test"
    assert mailbox.sent[0]["subject"].startswith("[WCW REFERRAL REVIEW]")
    assert mailbox.sent[0]["html_body"] == mailbox.sent[1]["html_body"]
    assert (tmp_path / "review-email.html").is_file()
    assert (tmp_path / "review-email.txt").is_file()
    assert "CONFIRMED " in (tmp_path / "review-email.txt").read_text(encoding="utf-8")


def test_workflow_entity_uses_canonical_referral_id(tmp_path) -> None:
    from referral_pipeline.review.workflow import _workflow_entity_id

    canonical = tmp_path / "canonical-referral.json"
    _write(canonical, {"referral_id": "ref_source_hash"})

    assert _workflow_entity_id(canonical, fallback_digest="artifact-hash") == "ref_source_hash"
