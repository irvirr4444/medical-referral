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
