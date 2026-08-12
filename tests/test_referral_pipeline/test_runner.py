from __future__ import annotations

import sqlite3
from pathlib import Path

from Outlook.mail import InboundPdfAttachment
from intake_extractor.canonical_referral import CanonicalExtractionError
from intake_extractor.llm.reliability import CapacityExhaustedError
from referral_pipeline import runner
from referral_pipeline.state import InboxState, STATUS_FAILED, STATUS_PENDING_RETRY


def test_review_recipient_defaults_to_referral_sender(monkeypatch) -> None:
    monkeypatch.delenv("REVIEW_RECIPIENT_EMAIL", raising=False)
    args = runner._parse_args(
        [
            "--process-retries",
            "--output-dir",
            "out",
            "--state-db",
            "state.sqlite",
        ]
    )

    attachment = InboundPdfAttachment(
        "outlook-graph",
        "message-1",
        "attachment-1",
        "referral.pdf",
        b"%PDF-1.4\n",
        sender="external@example.test",
    )
    assert runner._review_recipient(
        options={"source_sender": "external@example.test"},
        args=args,
        attachment=attachment,
        manifest={"source_sender": "external@example.test"},
    ) == "external@example.test"


def test_outlook_poll_includes_unfinished_ledger_jobs(tmp_path) -> None:
    state = InboxState(tmp_path / "state.sqlite")
    attachment = InboundPdfAttachment(
        "outlook-graph",
        "message-1",
        "attachment-1",
        "referral.pdf",
        b"%PDF-1.4\n",
    )

    assert runner._attachment_needs_processing(state, attachment)
    state.enqueue(attachment, artifact_path=tmp_path / "referral.pdf")
    assert runner._attachment_needs_processing(state, attachment)
    claimed = state.claim_job(attachment)
    assert claimed is not None
    assert not runner._attachment_needs_processing(state, attachment)
    state.mark_retryable_failure(claimed, error="temporary", error_kind="capacity")
    assert runner._attachment_needs_processing(state, attachment)


def test_permanent_review_failure_replies_in_original_thread(tmp_path, monkeypatch) -> None:
    pdf = tmp_path / "referral.pdf"
    pdf.write_bytes(b"%PDF-1.4\nsynthetic")
    attachment = InboundPdfAttachment(
        "outlook-graph",
        "message-1",
        "attachment-1",
        "referral.pdf",
        pdf.read_bytes(),
        sender="external@example.test",
        conversation_id="conversation-1",
    )
    state = InboxState(tmp_path / "state.sqlite")
    state.enqueue(
        attachment,
        artifact_path=pdf,
        options={"send_review": True, "source_sender": "external@example.test"},
    )
    job = state.claim_job(attachment)
    assert job is not None
    sent: list[dict] = []

    class FakeMailbox:
        def __init__(self, _client) -> None:
            pass

        def send_reply(self, **kwargs) -> None:
            sent.append(kwargs)

    monkeypatch.setattr(runner, "OutlookReviewMailbox", FakeMailbox)
    monkeypatch.setattr(
        runner,
        "process_inbound_pdf",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("unsupported referral")),
    )
    args = runner._parse_args(
        [
            "--process-retries",
            "--send-review",
            "--output-dir",
            str(tmp_path / "out"),
            "--state-db",
            str(tmp_path / "state.sqlite"),
        ]
    )

    result = runner.process_claimed_job(
        job,
        state=state,
        args=args,
        graph_client=object(),
    )

    assert result["status"] == STATUS_FAILED
    assert result["failure_reply_sent"] is True
    assert sent[0]["source_message_id"] == "message-1"
    assert sent[0]["recipient"] == "external@example.test"
    assert "could not complete this referral" in sent[0]["text_body"]

    monkeypatch.setenv("REVIEW_RECIPIENT_EMAIL", "internal@example.test")
    assert runner._review_recipient(
        options={"source_sender": "external@example.test"},
        args=args,
        attachment=attachment,
        manifest={"source_sender": "external@example.test"},
    ) == "external@example.test"


def test_database_failure_never_tells_sender_to_resend_pdf(tmp_path, monkeypatch) -> None:
    pdf = tmp_path / "referral.pdf"
    pdf.write_bytes(b"%PDF-1.4\nsynthetic")
    attachment = InboundPdfAttachment(
        "outlook-graph",
        "message-1",
        "attachment-1",
        "referral.pdf",
        pdf.read_bytes(),
        sender="external@example.test",
    )
    state = InboxState(tmp_path / "state.sqlite")
    state.enqueue(
        attachment,
        artifact_path=pdf,
        options={"send_review": True, "source_sender": "external@example.test"},
    )
    job = state.claim_job(attachment)
    assert job is not None
    sent: list[dict] = []

    class FakeMailbox:
        def __init__(self, _client) -> None:
            pass

        def send_reply(self, **kwargs) -> None:
            sent.append(kwargs)

    monkeypatch.setattr(runner, "OutlookReviewMailbox", FakeMailbox)
    monkeypatch.setattr(
        runner,
        "process_inbound_pdf",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            sqlite3.IntegrityError("duplicate workflow case")
        ),
    )
    args = runner._parse_args(
        [
            "--process-retries",
            "--send-review",
            "--output-dir",
            str(tmp_path / "out"),
            "--state-db",
            str(tmp_path / "state.sqlite"),
        ]
    )

    result = runner.process_claimed_job(
        job,
        state=state,
        args=args,
        graph_client=object(),
    )

    assert result["status"] == STATUS_FAILED
    assert result["failure_reply_sent"] is False
    assert sent == []


def test_process_claimed_job_defers_capacity_failures(tmp_path, monkeypatch) -> None:
    pdf = tmp_path / "referral.pdf"
    pdf.write_bytes(b"%PDF-1.4\nsynthetic")
    attachment = InboundPdfAttachment(
        "outlook-graph",
        "message-1",
        "attachment-1",
        "referral.pdf",
        pdf.read_bytes(),
    )
    state = InboxState(tmp_path / "state.sqlite", random_source=lambda: 1.0, max_attempts=5)
    state.enqueue(attachment, artifact_path=pdf, options={"send_review": False})
    job = state.claim_job(attachment)
    assert job is not None

    def boom(*_args, **_kwargs):
        raise CanonicalExtractionError("capacity exhausted") from CapacityExhaustedError(
            "exhausted",
            models_attempted=["claude-opus-5"],
        )

    monkeypatch.setattr(runner, "process_inbound_pdf", boom)
    args = runner._parse_args(
        [
            "--process-retries",
            "--output-dir",
            str(tmp_path / "out"),
            "--state-db",
            str(tmp_path / "state.sqlite"),
        ]
    )

    result = runner.process_claimed_job(job, state=state, args=args, graph_client=None)

    assert result["status"] == STATUS_PENDING_RETRY
    assert result["next_attempt_at"]
    updated = state.get_job(attachment)
    assert updated is not None
    assert updated.status == STATUS_PENDING_RETRY
    assert not list(Path(tmp_path).rglob("review-email.txt"))


def test_first_email_failure_does_not_block_later_emails(tmp_path, monkeypatch) -> None:
    first = InboundPdfAttachment(
        "outlook-graph",
        "message-1",
        "attachment-1",
        "first.pdf",
        b"%PDF-1.4\nfirst",
    )
    second = InboundPdfAttachment(
        "outlook-graph",
        "message-2",
        "attachment-2",
        "second.pdf",
        b"%PDF-1.4\nsecond",
    )

    monkeypatch.setattr(runner, "_attachments", lambda _args, **_kwargs: [first, second])

    def fake_process(attachment, **_kwargs):
        if attachment.filename == "first.pdf":
            raise ValueError("permanent extraction failure")
        return {
            "filename": attachment.filename,
            "attachment_sha256": attachment.sha256,
            "outcome": "ready_for_human_approval",
            "master_sheet_blocked": False,
            "preview_path": str(tmp_path / "preview.json"),
        }

    monkeypatch.setattr(runner, "process_inbound_pdf", fake_process)

    exit_code = runner.main(
        [
            "--eml",
            str(tmp_path / "unused.eml"),
            "--output-dir",
            str(tmp_path / "out"),
            "--state-db",
            str(tmp_path / "state.sqlite"),
            "--verbose",
        ]
    )

    assert exit_code == 1
    state = InboxState(tmp_path / "state.sqlite")
    failed_job = state.get_job(first)
    assert failed_job is not None
    assert failed_job.status == STATUS_FAILED
    assert state.is_completed(second)
    summary = (tmp_path / "out" / "run-summary.json").read_text(encoding="utf-8")
    assert "failed" in summary
    assert "completed" in summary
