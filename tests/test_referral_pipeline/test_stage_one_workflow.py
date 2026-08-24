from __future__ import annotations

import json
from datetime import datetime, timezone

from Outlook.mail import InboundPdfAttachment
from referral_pipeline.api.intake_inbox import IntakeInboxFeed
from referral_pipeline.monitoring.sqlite_store import SQLiteWorkflowStore
from referral_pipeline.stage_one.acknowledgement import send_partner_acknowledgement
from referral_pipeline.stage_one.tracker import StageOneTracker


NOW = datetime(2026, 8, 12, 12, 0, tzinfo=timezone.utc)


def _attachment() -> InboundPdfAttachment:
    return InboundPdfAttachment(
        source="outlook-graph",
        message_id="message-1",
        attachment_id="attachment-1",
        filename="referral.pdf",
        content=b"%PDF-1.4\nsynthetic",
        received_at=NOW.isoformat(),
        subject="Referral",
        sender="partner@example.test",
        conversation_id="conversation-1",
    )


def _manifest(tmp_path) -> dict:
    plan = {
        "referral": {
            "patient_name": "TEST Patient",
            "patient_dob": "01/02/1960",
            "patient_phone": "555-0100",
            "patient_address": "1 Test Street",
            "referring_facility": "TEST Facility",
            "diagnosis_text": "Synthetic wound",
            "insurance_provider": "TEST Insurance",
        },
        "validation": {
            "threshold_missing": [],
            "supporting_missing": [],
            "field_labels": {},
        },
    }
    path = tmp_path / "intake-plan.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    return {
        "plan_path": str(path),
        "referral_id": "ref_test",
        "outcome": "ready_for_human_approval",
        "duplicate_status": "no_candidates_found",
    }


def test_stage_one_case_and_timeline_are_idempotent(tmp_path) -> None:
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    tracker = StageOneTracker(store)
    attachment = _attachment()

    case = tracker.discover(attachment)
    tracker.discover(attachment)
    case = tracker.processing_started(case)
    case = tracker.extraction_completed(case, _manifest(tmp_path))

    stored = store.workflow_case(case.case_id)
    assert stored is not None
    assert stored.patient_label == "TEST Patient"
    assert stored.status == "processing"
    assert [event.event_type for event in store.list_events(case.case_id)] == [
        "referral_received",
        "extraction_started",
        "extraction_completed",
        "monday_duplicate_checked",
    ]


def test_same_pdf_in_a_second_email_is_a_separate_duplicate_candidate(tmp_path) -> None:
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    tracker = StageOneTracker(store)
    original = _attachment()
    repeated = InboundPdfAttachment(
        **{
            **original.__dict__,
            "message_id": "message-2",
            "attachment_id": "attachment-2",
        }
    )

    first = tracker.discover(original)
    second = tracker.discover(repeated)
    first = tracker.extraction_completed(first, _manifest(tmp_path))
    second = tracker.extraction_completed(second, _manifest(tmp_path))

    assert first.case_id != second.case_id
    assert first.referral_id == second.referral_id == "ref_test"
    assert first.attachment_sha256 == second.attachment_sha256
    assert len(store.list_workflow_cases()) == 2


def test_acknowledgement_claim_recovers_failure_but_never_resends_sent(tmp_path) -> None:
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    case = StageOneTracker(store).discover(_attachment())
    digest = "a" * 64

    assert store.claim_acknowledgement(
        case.case_id, recipient="partner@example.test", payload_digest=digest
    ) == "claimed"
    assert store.claim_acknowledgement(
        case.case_id, recipient="partner@example.test", payload_digest=digest
    ) == "busy"
    store.mark_acknowledgement_failed(case.case_id, "temporary")
    assert store.claim_acknowledgement(
        case.case_id, recipient="partner@example.test", payload_digest=digest
    ) == "claimed"
    store.mark_acknowledgement_sent(case.case_id)
    assert store.claim_acknowledgement(
        case.case_id, recipient="partner@example.test", payload_digest=digest
    ) == "already_sent"


def test_partner_acknowledgement_is_sent_once(tmp_path) -> None:
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    tracker = StageOneTracker(store)
    case = tracker.discover(_attachment())
    sent: list[dict] = []

    class Mailbox:
        def send_reply(self, **kwargs) -> None:
            sent.append(kwargs)

    for _ in range(2):
        send_partner_acknowledgement(
            case=case,
            manifest=_manifest(tmp_path),
            recipient="partner@example.test",
            source_message_id="message-1",
            mailbox=Mailbox(),
            store=store,
            tracker=tracker,
        )

    assert len(sent) == 1
    assert "received the referral" in sent[0]["text_body"]
    assert store.workflow_case(case.case_id).status == "completed"
    assert [event.event_type for event in store.list_events(case.case_id)].count(
        "partner_acknowledgement_sent"
    ) == 1


def test_partner_contact_request_is_a_valid_persisted_state(tmp_path) -> None:
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    tracker = StageOneTracker(store)
    case = tracker.discover(_attachment())

    stored = tracker.contact_confirmation_requested(
        case,
        recipient="partner@example.test",
        review_id="review-synthetic",
    )

    assert stored.status == "awaiting_partner_contact"
    assert store.workflow_case(case.case_id).status == "awaiting_partner_contact"


def test_reprocessing_does_not_reopen_a_completed_stage_one_case(tmp_path) -> None:
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    tracker = StageOneTracker(store)
    case = tracker.discover(_attachment())
    case = tracker.acknowledgement_sent(case, recipient="partner@example.test")

    case = tracker.processing_started(case)
    case = tracker.extraction_completed(case, _manifest(tmp_path))

    assert case.status == "completed"


def test_inbox_projection_exposes_persisted_stage_one_steps(tmp_path) -> None:
    attachment = _attachment()
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    tracker = StageOneTracker(store)
    case = tracker.discover(attachment)
    tracker.extraction_completed(case, _manifest(tmp_path))

    class Graph:
        def list_inbox_pdf_metadata(self, *, max_messages: int):
            from Outlook.mail import InboundPdfMetadata

            return [
                InboundPdfMetadata(
                    message_id=attachment.message_id,
                    attachment_id=attachment.attachment_id,
                    filename=attachment.filename,
                    received_at=attachment.received_at,
                    subject=attachment.subject,
                    sender=attachment.sender,
                )
            ]

    feed = IntakeInboxFeed(lambda: Graph(), workflow_store=store)
    referral = feed.read(limit=10, force=True)["referrals"][0]

    assert referral["case_id"] == case.case_id
    assert referral["patient_label"] == "TEST Patient"
    assert referral["persistence"] == "sqlite"
    assert referral["steps"]["extract-and-verify"]["status"] == "done"
    assert referral["steps"]["check-monday"]["status"] == "done"
    assert feed.read_timeline(referral["id"])["case"]["case_id"] == case.case_id


def test_retry_revisions_insert_new_events_instead_of_ignoring_duplicates(tmp_path) -> None:
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    tracker = StageOneTracker(store)
    case = tracker.discover(_attachment())
    case = tracker.processing_started(case, revision=1)
    case = tracker.extraction_completed(case, _manifest(tmp_path), revision=1)
    tracker.failed(case, event_type="stage_one_failed", error_code="OutlookGraphError", revision=1)
    tracker.extraction_completed(case, _manifest(tmp_path), revision=2)

    events = store.list_events(case.case_id)
    keys = [event.event_key for event in events]
    assert any(key.endswith("extraction-completed:rev1") for key in keys)
    assert any(key.endswith("extraction-completed:rev2") for key in keys)
    assert any(key.endswith("stage_one_failed:rev1") for key in keys)
    assert sum(event.event_type == "extraction_completed" for event in events) == 2
