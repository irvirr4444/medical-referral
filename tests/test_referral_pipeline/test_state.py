from __future__ import annotations

from datetime import datetime, timedelta, timezone

from Outlook.mail import InboundPdfAttachment
from referral_pipeline.state import (
    CIRCUIT_HALF_OPEN,
    CIRCUIT_OPEN,
    InboxState,
    STATUS_PENDING_RETRY,
    STATUS_PROCESSING,
)


def _attachment(name: str = "referral.pdf", content: bytes = b"%PDF-1.4\none") -> InboundPdfAttachment:
    return InboundPdfAttachment("outlook-graph", "message-1", "attachment-1", name, content)


def test_inbox_state_prevents_reprocessing_same_attachment(tmp_path) -> None:
    attachment = _attachment()
    state = InboxState(tmp_path / "state.sqlite")

    assert not state.is_completed(attachment)
    state.mark(attachment, status="completed")
    assert state.is_completed(attachment)


def test_migrate_failed_rows_to_pending_retry(tmp_path) -> None:
    db = tmp_path / "state.sqlite"
    import sqlite3

    with sqlite3.connect(db) as connection:
        connection.execute(
            """
            CREATE TABLE processed_attachments (
                source TEXT NOT NULL,
                message_id TEXT NOT NULL,
                attachment_id TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                status TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (source, message_id, attachment_id, sha256)
            )
            """
        )
        connection.execute(
            """
            INSERT INTO processed_attachments VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("outlook-graph", "message-1", "attachment-1", "abc", "failed", "2026-08-05T00:00:00+00:00"),
        )
        connection.execute("PRAGMA user_version = 1")

    state = InboxState(db)
    with sqlite3.connect(db) as connection:
        row = connection.execute("SELECT status FROM processed_attachments").fetchone()
        version = connection.execute("PRAGMA user_version").fetchone()[0]
    assert row[0] == STATUS_PENDING_RETRY
    assert version == 2
    assert state.due_count() >= 0


def test_enqueue_claim_and_complete_lifecycle(tmp_path) -> None:
    clock = {"now": datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc)}
    state = InboxState(tmp_path / "state.sqlite", clock=lambda: clock["now"], random_source=lambda: 1.0)
    attachment = _attachment()
    pdf = tmp_path / "referral.pdf"
    pdf.write_bytes(attachment.content)

    queued = state.enqueue(attachment, artifact_path=pdf, options={"send_review": True})
    assert queued is not None
    assert queued.status == "discovered"

    claimed = state.claim_job(attachment)
    assert claimed is not None
    assert claimed.status == STATUS_PROCESSING
    assert claimed.attempt_count == 1

    state.mark_completed(claimed)
    assert state.is_completed(attachment)
    assert state.enqueue(attachment, artifact_path=pdf) is None


def test_retryable_failure_schedules_next_attempt_and_opens_circuit(tmp_path) -> None:
    clock = {"now": datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc)}
    state = InboxState(
        tmp_path / "state.sqlite",
        clock=lambda: clock["now"],
        random_source=lambda: 1.0,
        circuit_failure_threshold=2,
        circuit_cooldown_seconds=60,
        max_attempts=5,
    )
    attachment = _attachment()
    pdf = tmp_path / "referral.pdf"
    pdf.write_bytes(attachment.content)
    state.enqueue(attachment, artifact_path=pdf, options={})
    first = state.claim_job(attachment)
    assert first is not None

    deferred = state.mark_retryable_failure(first, error="Overloaded", error_kind="capacity")
    assert deferred.status == STATUS_PENDING_RETRY
    assert deferred.next_attempt_at is not None

    clock["now"] = datetime.fromisoformat(deferred.next_attempt_at) + timedelta(seconds=1)
    second = state.claim_job(attachment)
    assert second is not None
    state.mark_retryable_failure(second, error="Overloaded again", error_kind="capacity")
    assert state.circuit_state() == CIRCUIT_OPEN
    assert state.claim_due(limit=1) == []

    clock["now"] = clock["now"] + timedelta(seconds=61)
    assert state.circuit_state() == CIRCUIT_HALF_OPEN


def test_expired_lease_returns_to_pending_retry(tmp_path) -> None:
    clock = {"now": datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc)}
    state = InboxState(
        tmp_path / "state.sqlite",
        clock=lambda: clock["now"],
        random_source=lambda: 1.0,
        lease_seconds=30,
    )
    attachment = _attachment()
    pdf = tmp_path / "referral.pdf"
    pdf.write_bytes(attachment.content)
    state.enqueue(attachment, artifact_path=pdf)
    claimed = state.claim_job(attachment)
    assert claimed is not None

    clock["now"] = clock["now"] + timedelta(seconds=31)
    recovered = state.recover_expired_leases()
    assert recovered == 1
    job = state.get_job(attachment)
    assert job is not None
    assert job.status == STATUS_PENDING_RETRY


def test_terminal_failure_after_max_attempts(tmp_path) -> None:
    state = InboxState(tmp_path / "state.sqlite", random_source=lambda: 1.0, max_attempts=1)
    attachment = _attachment()
    pdf = tmp_path / "referral.pdf"
    pdf.write_bytes(attachment.content)
    state.enqueue(attachment, artifact_path=pdf)
    claimed = state.claim_job(attachment)
    assert claimed is not None
    failed = state.mark_retryable_failure(claimed, error="still overloaded", error_kind="capacity")
    assert failed.status == "failed"


def test_permanent_failure_is_preserved_until_explicit_requeue(tmp_path) -> None:
    state = InboxState(tmp_path / "state.sqlite", random_source=lambda: 1.0, max_attempts=1)
    attachment = _attachment()
    pdf = tmp_path / "referral.pdf"
    pdf.write_bytes(attachment.content)
    state.enqueue(attachment, artifact_path=pdf)
    claimed = state.claim_job(attachment)
    assert claimed is not None
    state.mark_terminal_failure(claimed, error="bad pdf", error_kind="permanent")

    rediscovered = state.enqueue(attachment, artifact_path=pdf)
    assert rediscovered is not None
    assert rediscovered.status == "failed"
    assert state.claim_job(attachment) is None
    assert state.failed_count() == 1
    listed = state.list_failed()
    assert listed[0].sha256 == attachment.sha256
    assert listed[0].last_error == "bad pdf"

    requeued = state.requeue_failed(sha256=attachment.sha256)
    assert requeued.status == "discovered"
    assert requeued.attempt_count == 0
    assert state.failed_count() == 0
    assert state.claim_job(attachment) is not None


def test_requeue_preserves_options_until_explicit_refresh(tmp_path) -> None:
    from Outlook.mail import InboundPdfAttachment

    state = InboxState(tmp_path / "state.sqlite", random_source=lambda: 1.0, max_attempts=1)
    attachment = InboundPdfAttachment(
        "outlook-graph",
        "message-1",
        "attachment-1",
        "referral.pdf",
        b"%PDF-1.4\n",
    )
    pdf = tmp_path / "referral.pdf"
    pdf.write_bytes(attachment.content)
    state.enqueue(
        attachment,
        artifact_path=pdf,
        options={"monday_mode": "disabled", "drk_duplicate_check": False, "workflow_database_backend": "sqlite"},
    )
    claimed = state.claim_job(attachment)
    assert claimed is not None
    state.mark_terminal_failure(claimed, error="temporary", error_kind="permanent")
    requeued = state.requeue_failed(sha256=attachment.sha256)
    assert requeued.options["monday_mode"] == "disabled"
    assert requeued.options["drk_duplicate_check"] is False
    refreshed = state.refresh_options(
        sha256=attachment.sha256,
        options={"monday_mode": "live-readonly", "drk_duplicate_check": True, "workflow_database_backend": "supabase"},
    )
    assert refreshed.options["monday_mode"] == "live-readonly"
    assert refreshed.options["drk_duplicate_check"] is True
    assert refreshed.options["workflow_database_backend"] == "sqlite"
