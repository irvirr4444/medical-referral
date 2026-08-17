from __future__ import annotations

from types import SimpleNamespace

from Outlook.review_mail import ReviewReply
from referral_pipeline.monitoring.sqlite_store import SQLiteWorkflowStore
from referral_pipeline.review.store import ReviewStore
from referral_pipeline.review.workflow import ApprovalProcessor, artifact_digest
from referral_pipeline.stage_one.tracker import StageOneTracker


class FakeMailbox:
    def __init__(self, replies):
        self.replies = replies
        self.sent = []

    def list_replies(self, *, max_messages: int = 25):
        return self.replies[:max_messages]

    def send_reply(self, **kwargs):
        self.sent.append(kwargs)


def _write(path, value) -> None:
    import json

    path.write_text(json.dumps(value), encoding="utf-8")


def _partner_review(tmp_path, workflow_store):
    paths = []
    for name in ("canonical.json", "plan.json", "monday.json", "drk.json"):
        path = tmp_path / name
        _write(path, {"blocked": False})
        paths.append(path)
    tracker = StageOneTracker(workflow_store)
    case = tracker.discover(
        SimpleNamespace(
            message_id="source-message",
            attachment_id="attachment-1",
            source="outlook-graph",
            sha256="a" * 64,
            received_at="2026-08-12T09:00:00+00:00",
            safe_filename="referral.pdf",
            filename="referral.pdf",
            sender="partner@example.test",
        )
    )
    state_db = tmp_path / "state.sqlite"
    ReviewStore(state_db).add(
        review_id="review_partner_contact",
        token="internal-token",
        recipient="reviewer@example.test",
        artifact_digest=artifact_digest(paths),
        canonical_path=str(paths[0]),
        intake_plan_path=str(paths[1]),
        monday_preview_path=str(paths[2]),
        drk_draft_path=str(paths[3]),
        source_message_id="source-message",
        source_conversation_id="conversation-1",
        purpose="partner_contact",
        workflow_case_id=case.case_id,
    )
    mailbox = FakeMailbox(
        [
            ReviewReply(
                message_id="reply-contacted",
                sender="reviewer@example.test",
                subject="Re: referral follow-up",
                received_at="2099-08-12T10:00:00+00:00",
                conversation_id="conversation-1",
                text="Confirm",
            )
        ]
    )
    return state_db, mailbox, case


def test_confirmation_is_retried_until_workflow_advances(tmp_path) -> None:
    workflow_store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    state_db, mailbox, case = _partner_review(tmp_path, workflow_store)

    class BoomStore:
        def __init__(self, inner) -> None:
            self._inner = inner
            self.failures = 1

        def __getattr__(self, name: str):
            return getattr(self._inner, name)

        def upsert_work_item(self, item):
            if self.failures:
                self.failures -= 1
                self._inner.upsert_work_item(item)
                raise RuntimeError("assignment write failed")
            return self._inner.upsert_work_item(item)

    wrapped = BoomStore(workflow_store)
    first = ApprovalProcessor(
        state_db=state_db,
        mailbox=mailbox,
        workflow_store=wrapped,
        allow_supabase_store=False,
    ).poll()

    review = ReviewStore(state_db).get("review_partner_contact")
    assert first["partner_contact_confirmations"] == ["review_partner_contact"]
    assert review.status == "partner_contact_confirmed"
    assert review.workflow_apply_status == "failed"
    assert ReviewStore(state_db).response_exists("reply-contacted")

    mailbox.replies = []
    second = ApprovalProcessor(
        state_db=state_db,
        mailbox=mailbox,
        workflow_store=wrapped,
        allow_supabase_store=False,
    ).poll()
    assert second["partner_contact_confirmations"] == []
    assert second["workflow_applies"][0]["status"] == "applied"
    stored = workflow_store.workflow_case(case.case_id)
    assert stored is not None
    assert stored.current_stage == 2
    assert ReviewStore(state_db).get("review_partner_contact").workflow_apply_status == "applied"


def test_duplicate_outlook_replies_do_not_duplicate_workflow_side_effects(tmp_path) -> None:
    workflow_store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    state_db, mailbox, case = _partner_review(tmp_path, workflow_store)
    processor = ApprovalProcessor(
        state_db=state_db,
        mailbox=mailbox,
        workflow_store=workflow_store,
        allow_supabase_store=False,
    )
    first = processor.poll()
    second = processor.poll()
    assert first["partner_contact_confirmations"] == ["review_partner_contact"]
    assert second["duplicate_response_messages"] == ["reply-contacted"]
    assert len(workflow_store.list_work_items(case_id=case.case_id, stage=2)) == 1
    assert len(
        [
            event
            for event in workflow_store.list_events(case.case_id)
            if event.event_type == "partner_contact_confirmed"
        ]
    ) == 1


def test_missing_workflow_store_marks_apply_failed(tmp_path) -> None:
    workflow_store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    state_db, mailbox, _case = _partner_review(tmp_path, workflow_store)
    first = ApprovalProcessor(
        state_db=state_db,
        mailbox=mailbox,
        workflow_store=None,
        allow_supabase_store=False,
    ).poll()
    review = ReviewStore(state_db).get("review_partner_contact")
    assert first["workflow_applies"][0]["status"] == "failed"
    assert review.workflow_apply_status == "failed"
    assert "workflow store is required" in (review.workflow_apply_last_error or "")


def test_missing_workflow_case_id_marks_apply_failed(tmp_path) -> None:
    workflow_store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    state_db, mailbox, _case = _partner_review(tmp_path, workflow_store)
    import sqlite3

    with sqlite3.connect(state_db) as connection:
        connection.execute(
            "UPDATE referral_reviews SET workflow_case_id = NULL WHERE review_id = ?",
            ("review_partner_contact",),
        )
    result = ApprovalProcessor(
        state_db=state_db,
        mailbox=mailbox,
        workflow_store=workflow_store,
        allow_supabase_store=False,
    ).poll()
    review = ReviewStore(state_db).get("review_partner_contact")
    assert result["workflow_applies"][0]["status"] == "failed"
    assert review.workflow_apply_status == "failed"
    assert "workflow_case_id" in (review.workflow_apply_last_error or "")


def test_missing_workflow_case_marks_apply_failed_and_retries(tmp_path) -> None:
    workflow_store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    state_db, mailbox, case = _partner_review(tmp_path, workflow_store)
    import sqlite3

    with sqlite3.connect(state_db) as connection:
        connection.execute(
            "UPDATE referral_reviews SET workflow_case_id = ? WHERE review_id = ?",
            ("case_missing", "review_partner_contact"),
        )
    processor = ApprovalProcessor(
        state_db=state_db,
        mailbox=mailbox,
        workflow_store=workflow_store,
        allow_supabase_store=False,
    )
    first = processor.poll()
    assert first["workflow_applies"][0]["status"] == "failed"
    with sqlite3.connect(state_db) as connection:
        connection.execute(
            "UPDATE referral_reviews SET workflow_case_id = ? WHERE review_id = ?",
            (case.case_id, "review_partner_contact"),
        )
    mailbox.replies = []
    second = processor.poll()
    assert second["workflow_applies"][0]["status"] == "applied"
    stored = workflow_store.workflow_case(case.case_id)
    assert stored is not None
    assert stored.current_stage == 2
