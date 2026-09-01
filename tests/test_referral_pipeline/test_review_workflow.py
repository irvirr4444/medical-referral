from __future__ import annotations

import json
from types import SimpleNamespace

from Outlook.review_mail import ReviewReply
from referral_pipeline.review.store import ReviewStore
from referral_pipeline.review.workflow import ApprovalProcessor, artifact_digest
from referral_pipeline.monitoring.sqlite_store import SQLiteWorkflowStore
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
    path.write_text(json.dumps(value), encoding="utf-8")


def test_human_confirmation_runs_dry_run_once_and_sends_success_reply(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MONDAY_DOT_COM_API_KEY", "test-key")
    canonical = tmp_path / "canonical-referral.json"
    plan = tmp_path / "intake-plan.json"
    preview = tmp_path / "master-sheet-preview.json"
    drk = tmp_path / "drk-create-draft.json"
    _write(canonical, {"referral_id": "ref_test"})
    _write(plan, {"outcome": "ready_for_human_approval"})
    _write(
        preview,
        {
            "operation": "create_item",
            "board_id": 123,
            "group_id": "new",
            "item_name": "TEST Jamie Tester",
            "column_values": {},
            "blocked": False,
        },
    )
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
        source_conversation_id="conversation-1",
    )
    mailbox = FakeMailbox(
        [
            ReviewReply(
                message_id="reply-1",
                sender="reviewer@example.test",
                subject="Re: review",
                received_at="2099-08-05T12:00:00+00:00",
                conversation_id="conversation-1",
                text="Confirm",
            )
        ]
    )
    calls = []
    monkeypatch.setattr(
        "referral_pipeline.integrations.monday.master_sheet_writer.apply_master_sheet_create",
        lambda value: calls.append(value) or {"item": {"id": "monday-123"}, "applied_actions": []},
    )

    first = ApprovalProcessor(state_db=state_db, mailbox=mailbox).poll(dry_run=True)
    second = ApprovalProcessor(state_db=state_db, mailbox=mailbox).poll(dry_run=True)

    assert first["accepted_confirmations"] == ["review_abc123_xyz987"]
    assert first["executed"][0]["status"] == "dry_run_completed"
    assert first["executed"][0]["writes_performed"] is False
    assert calls == []
    assert second["executed"] == []
    dry_run = json.loads((tmp_path / "approval-dry-run.json").read_text(encoding="utf-8"))
    assert dry_run["monday"]["written"] is False
    assert dry_run["drk"]["written"] is False
    assert "No patient data was created" in mailbox.sent[0]["text_body"]
    assert ReviewStore(state_db).get("review_abc123_xyz987").status == "dry_run_completed"


def test_original_source_message_cannot_be_classified_as_confirmation(tmp_path) -> None:
    files = []
    for name in ("canonical.json", "plan.json", "monday.json", "drk.json"):
        path = tmp_path / name
        _write(path, {"blocked": False})
        files.append(path)
    state_db = tmp_path / "state.sqlite"
    ReviewStore(state_db).add(
        review_id="review_test",
        token="internal-token-value",
        recipient="sender@example.test",
        artifact_digest=artifact_digest(files),
        canonical_path=str(files[0]),
        intake_plan_path=str(files[1]),
        monday_preview_path=str(files[2]),
        drk_draft_path=str(files[3]),
        source_message_id="source-message",
        source_conversation_id="conversation-1",
    )
    mailbox = FakeMailbox(
        [
            ReviewReply(
                message_id="source-message",
                sender="sender@example.test",
                subject="Referral",
                received_at="2099-08-05T12:00:00+00:00",
                conversation_id="conversation-1",
                text="Please proceed with this referral",
            )
        ]
    )

    result = ApprovalProcessor(
        state_db=state_db,
        mailbox=mailbox,
        intent_classifier=lambda _text: (_ for _ in ()).throw(
            AssertionError("source email must not reach classifier")
        ),
    ).poll(execute=True)

    assert result["accepted_confirmations"] == []
    assert result["ignored_confirmations"][0]["reason"] == "message_predates_review_request"


def test_partner_contact_reply_completes_stage_one_without_destination_execution(tmp_path) -> None:
    paths = []
    for name in ("canonical.json", "plan.json", "monday.json", "drk.json"):
        path = tmp_path / name
        _write(path, {"blocked": False})
        paths.append(path)
    workflow_store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
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
                text="No answer, left voicemail",
            )
        ]
    )

    result = ApprovalProcessor(
        state_db=state_db,
        mailbox=mailbox,
        workflow_store=workflow_store,
    ).poll()

    assert result["partner_contact_confirmations"] == ["review_partner_contact"]
    assert result["partner_contact_outcomes"] == [
        {"review_id": "review_partner_contact", "outcome": "not_reached"}
    ]
    assert result["accepted_confirmations"] == []
    assert result["executed"] == []
    updated_case = workflow_store.workflow_case(case.case_id)
    assert updated_case is not None
    assert updated_case.current_stage == 2
    assert updated_case.status == "needs_attention"
    work_items = workflow_store.list_work_items(case_id=case.case_id, stage=2)
    assert len(work_items) == 1
    assert work_items[0].owner_role == "intake_team"
    assert work_items[0].status == "blocked"
    event = next(
        event
        for event in workflow_store.list_events(case.case_id)
        if event.event_type == "partner_contact_confirmed"
    )
    assert event.details["contact_outcome"] == "not_reached"


def test_execute_creates_monday_once_and_leaves_drk_pending(tmp_path, monkeypatch) -> None:
    files = []
    payloads = (
        {"referral_id": "ref_test"},
        {"outcome": "ready_for_human_approval"},
        {
            "operation": "create_item",
            "board_id": 123,
            "group_id": "new",
            "item_name": "TEST Jamie Tester",
            "column_values": {},
            "blocked": False,
        },
        {"ready_for_fill": True, "payload": {}, "blockers": []},
    )
    for name, payload in zip(
        ("canonical.json", "plan.json", "monday.json", "drk.json"),
        payloads,
        strict=True,
    ):
        path = tmp_path / name
        _write(path, payload)
        files.append(path)
    state_db = tmp_path / "state.sqlite"
    store = ReviewStore(state_db)
    store.add(
        review_id="review_execute",
        token="unused",
        recipient="sender@example.test",
        artifact_digest=artifact_digest(files),
        canonical_path=str(files[0]),
        intake_plan_path=str(files[1]),
        monday_preview_path=str(files[2]),
        drk_draft_path=str(files[3]),
        source_message_id="source-message",
        source_conversation_id="conversation-1",
    )
    assert store.confirm_by_context(
        review_id="review_execute",
        sender="sender@example.test",
        conversation_id="conversation-1",
        message_id="confirm-message",
    )
    calls = []

    def fake_apply(preview, *, on_item_created):
        calls.append(preview)
        item = {"id": "monday-123"}
        on_item_created(item)
        return {"item": item, "applied_actions": []}

    monkeypatch.setattr("referral_pipeline.integrations.monday.master_sheet_writer.apply_master_sheet_create", fake_apply)
    mailbox = FakeMailbox([])

    first = ApprovalProcessor(state_db=state_db, mailbox=mailbox).poll(execute=True)
    second = ApprovalProcessor(state_db=state_db, mailbox=mailbox).poll(execute=True)

    assert first["executed"][0]["status"] == "monday_applied_drk_pending"
    assert first["executed"][0]["writes_performed"] is True
    assert first["executed"][0]["monday_item_id"] == "monday-123"
    assert second["executed"] == []
    assert len(calls) == 1
    saved = ReviewStore(state_db).get("review_execute")
    assert saved.status == "monday_applied_drk_pending"
    assert saved.monday_item_id == "monday-123"
    assert saved.drk_status == "pending_draft"
    assert "DRK remains a pending draft" in mailbox.sent[0]["text_body"]


def test_execute_preserves_item_id_when_post_create_action_fails(tmp_path, monkeypatch) -> None:
    files = []
    payloads = (
        {"referral_id": "ref_test"},
        {"outcome": "ready_for_human_approval"},
        {
            "operation": "create_item",
            "board_id": 123,
            "group_id": "new",
            "item_name": "TEST Jamie Tester",
            "column_values": {},
            "blocked": False,
        },
        {"ready_for_fill": False, "payload": {}, "blockers": ["unfinished"]},
    )
    for name, payload in zip(
        ("canonical.json", "plan.json", "monday.json", "drk.json"),
        payloads,
        strict=True,
    ):
        path = tmp_path / name
        _write(path, payload)
        files.append(path)
    state_db = tmp_path / "state.sqlite"
    store = ReviewStore(state_db)
    store.add(
        review_id="review_partial",
        token="unused",
        recipient="sender@example.test",
        artifact_digest=artifact_digest(files),
        canonical_path=str(files[0]),
        intake_plan_path=str(files[1]),
        monday_preview_path=str(files[2]),
        drk_draft_path=str(files[3]),
        source_message_id="source-message",
        source_conversation_id="conversation-1",
    )
    assert store.confirm_by_context(
        review_id="review_partial",
        sender="sender@example.test",
        conversation_id="conversation-1",
        message_id="confirm-message",
    )

    def partial_failure(_preview, *, on_item_created):
        on_item_created({"id": "monday-456"})
        raise RuntimeError("post-create update failed")

    monkeypatch.setattr("referral_pipeline.integrations.monday.master_sheet_writer.apply_master_sheet_create", partial_failure)
    result = ApprovalProcessor(state_db=state_db, mailbox=FakeMailbox([])).poll(execute=True)

    assert result["executed"][0]["status"] == "monday_applied_drk_pending"
    assert result["executed"][0]["monday_item_id"] == "monday-456"
    assert result["executed"][0]["post_create_error"] == "post-create update failed"
    saved = ReviewStore(state_db).get("review_partial")
    assert saved.monday_item_id == "monday-456"
    assert saved.status == "monday_applied_drk_pending"


def test_dry_run_failure_is_audited_without_consuming_confirmation(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("MONDAY_DOT_COM_API_KEY", raising=False)
    files = []
    payloads = (
        {"referral_id": "ref_test"},
        {"outcome": "ready_for_human_approval"},
        {
            "operation": "create_item",
            "board_id": 123,
            "group_id": "new",
            "item_name": "TEST Jamie Tester",
            "column_values": {},
            "blocked": False,
        },
        {"ready_for_fill": True, "payload": {}, "blockers": []},
    )
    for name, payload in zip(
        ("canonical.json", "plan.json", "monday.json", "drk.json"),
        payloads,
        strict=True,
    ):
        path = tmp_path / name
        _write(path, payload)
        files.append(path)
    state_db = tmp_path / "state.sqlite"
    store = ReviewStore(state_db)
    store.add(
        review_id="review_dry_failure",
        token="unused",
        recipient="sender@example.test",
        artifact_digest=artifact_digest(files),
        canonical_path=str(files[0]),
        intake_plan_path=str(files[1]),
        monday_preview_path=str(files[2]),
        drk_draft_path=str(files[3]),
        source_message_id="source-message",
        source_conversation_id="conversation-1",
    )
    assert store.confirm_by_context(
        review_id="review_dry_failure",
        sender="sender@example.test",
        conversation_id="conversation-1",
        message_id="confirm-message",
    )

    result = ApprovalProcessor(state_db=state_db, mailbox=FakeMailbox([])).poll(dry_run=True)

    assert result["executed"][0]["status"] == "failed"
    assert result["executed"][0]["writes_performed"] is False
    saved = ReviewStore(state_db).get("review_dry_failure")
    assert saved.status == "confirmed"
    assert saved.last_dry_run_result["status"] == "dry_run_failed"


class RecordingMailbox:
    def __init__(self):
        self.sent = []

    def send_reply(self, *, source_message_id: str, recipient: str, text_body: str | None = None, html_body: str | None = None, content_type: str = "HTML", body: str | None = None) -> None:
        self.sent.append(
            {
                "source_message_id": source_message_id,
                "recipient": recipient,
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
        "source_conversation_id": "conversation-1",
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
    assert mailbox.sent[0]["source_message_id"] == "source-message"
    assert mailbox.sent[0]["html_body"] == mailbox.sent[1]["html_body"]
    assert (tmp_path / "review-email.html").is_file()
    assert (tmp_path / "review-email.txt").is_file()
    email_text = (tmp_path / "review-email.txt").read_text(encoding="utf-8")
    assert "Reply Confirm if the information is accurate" in email_text
    assert "CONFIRMED " not in email_text


def test_workflow_entity_uses_canonical_referral_id(tmp_path) -> None:
    from referral_pipeline.review.workflow import _workflow_entity_id

    canonical = tmp_path / "canonical-referral.json"
    _write(canonical, {"referral_id": "ref_source_hash"})

    assert _workflow_entity_id(canonical, fallback_digest="artifact-hash") == "ref_source_hash"
