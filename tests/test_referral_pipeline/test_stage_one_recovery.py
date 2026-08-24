from __future__ import annotations

from referral_pipeline.stage_one.recovery import (
    completed_subsystems,
    merge_refreshed_options,
    parse_retry_step,
    should_run_step,
)
from referral_pipeline.monitoring.models import WorkflowEvent
from datetime import datetime, timezone


NOW = datetime(2026, 8, 14, tzinfo=timezone.utc)


def test_full_retry_skips_completed_subsystems_and_reruns_the_named_step() -> None:
    completed = {"extraction", "monday"}
    assert should_run_step("extraction", retry_step="all", completed=completed) is False
    assert should_run_step("monday", retry_step="all", completed=completed) is False
    assert should_run_step("drk", retry_step="all", completed=completed) is True
    assert should_run_step("extraction", retry_step="extraction", completed=completed) is True
    assert should_run_step("drk", retry_step="extraction", completed=completed) is False
    assert should_run_step("monday", retry_step="monday", completed=completed) is True
    assert parse_retry_step(None) == "all"


def test_latest_event_projection_marks_completed_subsystems() -> None:
    events = [
        WorkflowEvent(
            event_key="extracted-rev1",
            event_type="extraction_completed",
            entity_id="case-1",
            source="extractor",
            occurred_at=NOW,
            details={"revision": 1},
        ),
        WorkflowEvent(
            event_key="failed-rev1",
            event_type="stage_one_failed",
            entity_id="case-1",
            source="pipeline",
            occurred_at=NOW,
            details={"revision": 1},
        ),
        WorkflowEvent(
            event_key="extracted-rev2",
            event_type="extraction_completed",
            entity_id="case-1",
            source="extractor",
            occurred_at=NOW,
            details={"revision": 2},
        ),
        WorkflowEvent(
            event_key="monday-rev2",
            event_type="monday_duplicate_checked",
            entity_id="case-1",
            source="monday",
            occurred_at=NOW,
            details={"revision": 2},
        ),
    ]
    assert completed_subsystems(events) == {"extraction", "monday"}


def test_merge_refreshed_options_keeps_identity_and_replaces_operator_flags() -> None:
    stored = {
        "workflow_database_backend": "sqlite",
        "synthetic_persistence_allowed": False,
        "source_sender": "partner@example.test",
        "source_conversation_id": "conversation-1",
        "monday_mode": "disabled",
        "drk_duplicate_check": False,
    }
    current = {
        "workflow_database_backend": "supabase",
        "synthetic_persistence_allowed": True,
        "source_sender": "other@example.test",
        "source_conversation_id": "conversation-2",
        "monday_mode": "live-readonly",
        "drk_duplicate_check": True,
        "send_review": True,
    }
    merged = merge_refreshed_options(stored, current)
    assert merged["workflow_database_backend"] == "sqlite"
    assert merged["synthetic_persistence_allowed"] is False
    assert merged["source_sender"] == "partner@example.test"
    assert merged["source_conversation_id"] == "conversation-1"
    assert merged["monday_mode"] == "live-readonly"
    assert merged["drk_duplicate_check"] is True
    assert merged["send_review"] is True


def test_next_event_revision_is_monotonic_and_ignores_retry_count() -> None:
    from referral_pipeline.stage_one.recovery import next_event_revision

    events = [
        WorkflowEvent(
            event_key="stage1:abc:extraction-completed:rev1",
            event_type="extraction_completed",
            entity_id="case-1",
            source="extractor",
            occurred_at=NOW,
            details={"revision": 1},
        ),
        WorkflowEvent(
            event_key="stage1:abc:stage_one_failed:rev1",
            event_type="stage_one_failed",
            entity_id="case-1",
            source="pipeline",
            occurred_at=NOW,
            details={"revision": 1},
        ),
    ]
    assert next_event_revision(events) == 2
    assert next_event_revision([]) == 1


def test_requeue_then_retry_records_rev2_and_ui_projects_it(tmp_path) -> None:
    from Outlook.mail import InboundPdfAttachment
    from referral_pipeline.api.intake_inbox import _step_projection
    from referral_pipeline.monitoring.sqlite_store import SQLiteWorkflowStore
    from referral_pipeline.stage_one.recovery import next_event_revision
    from referral_pipeline.stage_one.tracker import StageOneTracker
    from referral_pipeline.state import InboxState

    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    tracker = StageOneTracker(store)
    attachment = InboundPdfAttachment(
        "outlook-graph",
        "message-rev",
        "attachment-rev",
        "referral.pdf",
        b"%PDF-1.4\n",
    )
    pdf = tmp_path / "referral.pdf"
    pdf.write_bytes(attachment.content)
    state = InboxState(tmp_path / "state.sqlite", random_source=lambda: 1.0, max_attempts=1)
    state.enqueue(attachment, artifact_path=pdf)
    claimed = state.claim_job(attachment)
    assert claimed is not None
    case = tracker.discover(attachment)
    rev1 = next_event_revision(store.list_events(case.case_id))
    case = tracker.processing_started(case, revision=rev1)
    tracker.failed(case, event_type="stage_one_failed", error_code="Boom", revision=rev1)
    state.mark_terminal_failure(claimed, error="boom", error_kind="permanent")
    requeued = state.requeue_failed(sha256=attachment.sha256)
    assert requeued.attempt_count == 0
    rev2 = next_event_revision(store.list_events(case.case_id))
    assert rev2 == 2
    tracker.monday_checked(case, {"duplicate_status": "clear"}, revision=rev2)
    tracker.drk_checked(case, {"status": "clear"}, revision=rev2)
    tracker.extraction_completed(
        case,
        {
            "plan_path": str(tmp_path / "missing.json"),
            "outcome": "ready_for_human_approval",
            "duplicate_status": "clear",
        },
        revision=rev2,
    )
    events = store.list_events(case.case_id)
    keys = [event.event_key for event in events]
    assert any(key.endswith(":rev1") for key in keys)
    assert any("monday-duplicate:rev2" in key for key in keys)
    assert any("drk-duplicate:rev2" in key for key in keys)
    assert any("extraction-completed:rev2" in key for key in keys)
    steps = _step_projection(events, case_status="processing")
    assert steps["extract-and-verify"]["details"]["revision"] == 2
    assert steps["check-monday"]["details"]["revision"] == 2
    assert steps["check-drk"]["details"]["revision"] == 2
