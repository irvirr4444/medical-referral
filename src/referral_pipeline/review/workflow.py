"""Create review requests and execute strictly confirmed destination writes."""

from __future__ import annotations

import hashlib
import json
import secrets
from pathlib import Path
from typing import Any

from Outlook.review_mail import OutlookReviewMailbox
from referral_pipeline.review.commands import parse_approval_command
from referral_pipeline.review.store import ReviewStore
from referral_pipeline.review.summary import render_review_email
from referral_pipeline.monitoring.models import PatientLink, utc_now
from referral_pipeline.monitoring.observer import record_lifecycle_event


class ReviewWorkflowError(RuntimeError):
    pass


def create_and_send_review(
    manifest: dict[str, Any],
    *,
    recipient: str,
    write_config_path: str | Path,
    state_db: str | Path,
    mailbox: OutlookReviewMailbox,
) -> dict[str, Any]:
    recipient = recipient.strip()
    if not recipient:
        raise ReviewWorkflowError("review recipient cannot be empty")
    source_message_id = str(manifest.get("source_message_id") or "").strip()
    if not source_message_id:
        raise ReviewWorkflowError("source message ID is required to send the review as a reply")
    paths = _artifact_paths(manifest)
    digest = artifact_digest(paths.values())
    entity_id = _workflow_entity_id(paths["canonical"], fallback_digest=digest)
    store = ReviewStore(state_db)
    existing = store.find_active(
        artifact_digest=digest,
        source_message_id=source_message_id,
        recipient=recipient,
    )
    if existing is not None and (existing.email_html_body or existing.email_text_body or existing.email_body):
        subject = existing.email_subject or f"[WCW REFERRAL REVIEW] {existing.review_id}"
        content_type = (existing.email_content_type or ("HTML" if existing.email_html_body else "Text")).upper()
        html_body = existing.email_html_body
        text_body = existing.email_text_body or existing.email_body
        body_for_send = html_body if content_type == "HTML" and html_body else text_body
        review_id = existing.review_id
        confirmation_source = text_body or existing.email_body or ""
        review_status = (
            "awaiting_confirmation"
            if existing.status in {"awaiting_confirmation", "review_send_failed"}
            and "CONFIRMED " in confirmation_source
            else existing.status
        )
        if review_status == "review_send_failed":
            review_status = "awaiting_confirmation"
        try:
            mailbox.send_review(
                recipient=recipient,
                subject=subject,
                html_body=html_body,
                text_body=text_body,
                content_type=content_type,
                body=body_for_send,
            )
        except Exception as error:
            store.mark_failed(review_id, error=f"review email send failed: {error}", status="review_send_failed")
            raise
        store.mark_sent(
            review_id,
            status=review_status,
            email_subject=subject,
            email_html_body=html_body,
            email_text_body=text_body,
            email_content_type=content_type,
        )
        record_lifecycle_event(
            "review_requested",
            entity_id=entity_id,
            source="outlook",
            event_key=f"review-requested:{review_id}",
            details={"review_id": review_id, "recipient": recipient, "status": review_status, "reused": True},
        )
        audit_path = _write_review_audit(
            paths["monday"].parent,
            review_id=review_id,
            recipient=recipient,
            status=review_status,
            artifact_digest=digest,
            subject=subject,
            html_body=html_body,
            text_body=text_body or "",
            content_type=content_type,
            reused=True,
        )
        return {
            "review_id": review_id,
            "review_status": review_status,
            "review_recipient": recipient,
            "review_audit_path": str(audit_path),
            "review_reused": True,
            "review_content_type": content_type,
        }

    review_id = f"review_{digest[:12]}_{secrets.token_hex(3)}"
    token = secrets.token_urlsafe(18)
    preview = _load_json(paths["monday"])
    approval_allowed = not bool(preview.get("blocked"))
    review_status = "awaiting_confirmation" if approval_allowed else "needs_correction"
    email = render_review_email(
        review_id=review_id,
        token=token,
        canonical_path=paths["canonical"],
        intake_plan_path=paths["plan"],
        monday_preview_path=paths["monday"],
        drk_draft_path=paths["drk"],
        write_config_path=write_config_path,
        approval_allowed=approval_allowed,
    )
    store.add(
        review_id=review_id,
        token=token,
        recipient=recipient,
        artifact_digest=digest,
        canonical_path=str(paths["canonical"].resolve()),
        intake_plan_path=str(paths["plan"].resolve()),
        monday_preview_path=str(paths["monday"].resolve()),
        drk_draft_path=str(paths["drk"].resolve()),
        source_message_id=source_message_id,
        status=review_status,
        email_subject=email.subject,
        email_html_body=email.html_body,
        email_text_body=email.text_body,
        email_content_type=email.content_type,
    )
    try:
        mailbox.send_review(
            recipient=recipient,
            subject=email.subject,
            html_body=email.html_body,
            text_body=email.text_body,
            content_type=email.content_type,
        )
    except Exception as error:
        store.mark_failed(review_id, error=f"review email send failed: {error}", status="review_send_failed")
        raise

    record_lifecycle_event(
        "review_requested",
        entity_id=entity_id,
        source="outlook",
        event_key=f"review-requested:{review_id}",
        details={"review_id": review_id, "recipient": recipient, "status": review_status, "reused": False},
    )

    audit_path = _write_review_audit(
        paths["monday"].parent,
        review_id=review_id,
        recipient=recipient,
        status=review_status,
        artifact_digest=digest,
        subject=email.subject,
        html_body=email.html_body,
        text_body=email.text_body,
        content_type=email.content_type,
        reused=False,
    )
    return {
        "review_id": review_id,
        "review_status": review_status,
        "review_recipient": recipient,
        "review_audit_path": str(audit_path),
        "review_reused": False,
        "review_content_type": email.content_type,
    }


def _write_review_audit(
    output_dir: Path,
    *,
    review_id: str,
    recipient: str,
    status: str,
    artifact_digest: str,
    subject: str,
    html_body: str | None,
    text_body: str,
    content_type: str,
    reused: bool,
) -> Path:
    audit_path = output_dir / "review-request.json"
    text_path = output_dir / "review-email.txt"
    html_path = output_dir / "review-email.html"
    text_path.write_text(text_body, encoding="utf-8")
    if html_body:
        html_path.write_text(html_body, encoding="utf-8")
    audit_path.write_text(
        json.dumps(
            {
                "review_id": review_id,
                "recipient": recipient,
                "status": status,
                "artifact_digest": artifact_digest,
                "subject": subject,
                "content_type": content_type,
                "email_path": str(text_path),
                "html_email_path": str(html_path) if html_body else None,
                "reused": reused,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return audit_path


class ApprovalProcessor:
    def __init__(self, *, state_db: str | Path, mailbox: OutlookReviewMailbox) -> None:
        self.store = ReviewStore(state_db)
        self.mailbox = mailbox

    def poll(self, *, max_messages: int = 25, execute: bool = False) -> dict[str, Any]:
        accepted: list[str] = []
        ignored: list[dict[str, str]] = []
        for reply in self.mailbox.list_replies(max_messages=max_messages):
            command = parse_approval_command(reply.text)
            if command is None:
                continue
            if self.store.confirm(
                review_id=command.review_id,
                token=command.token,
                sender=reply.sender,
                message_id=reply.message_id,
            ):
                accepted.append(command.review_id)
                confirmed_review = self.store.get(command.review_id)
                record_lifecycle_event(
                    "review_confirmed",
                    entity_id=_workflow_entity_id(
                        Path(confirmed_review.canonical_path),
                        fallback_digest=confirmed_review.artifact_digest,
                    ),
                    source="outlook",
                    event_key=f"review-confirmed:{reply.message_id}",
                    details={"review_id": command.review_id, "confirmation_message_id": reply.message_id},
                )
            else:
                ignored.append({"message_id": reply.message_id, "reason": "authorization_or_state_mismatch"})

        applied: list[dict[str, Any]] = []
        if execute:
            for review in self.store.confirmed():
                try:
                    applied.append(self._apply(review.review_id))
                except Exception as error:
                    self.store.mark_failed(review.review_id, error=str(error))
                    applied.append({"review_id": review.review_id, "status": "failed", "error": str(error)})
        return {
            "accepted_confirmations": accepted,
            "ignored_confirmations": ignored,
            "executed": applied,
        }

    def _apply(self, review_id: str) -> dict[str, Any]:
        from master_sheet_writer import apply_master_sheet_create

        review = self.store.get(review_id)
        paths = [
            Path(review.canonical_path),
            Path(review.intake_plan_path),
            Path(review.monday_preview_path),
            Path(review.drk_draft_path),
        ]
        if artifact_digest(paths) != review.artifact_digest:
            raise ReviewWorkflowError("approved artifacts changed after the review email was sent")
        preview = _load_json(Path(review.monday_preview_path))
        if preview.get("blocked"):
            raise ReviewWorkflowError("approved Monday preview is blocked and cannot be applied")
        if not self.store.begin_monday_apply(review_id):
            raise ReviewWorkflowError("review is not in a confirmed state or is already being applied")

        output_dir = Path(review.monday_preview_path).parent
        result_path = output_dir / "master-sheet-apply-result.json"
        if result_path.exists():
            result = _load_json(result_path)
        else:
            result = apply_master_sheet_create({**preview, "mode": "apply"})
            result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        item = result.get("item") or {}
        item_id = str(item.get("id") or "")
        if not item_id:
            raise ReviewWorkflowError("Monday apply result did not contain an item ID")

        handoff_path = output_dir / "drk-handoff.json"
        handoff = {
            "review_id": review_id,
            "status": "pending_guarded_drk_execution",
            "monday_item_id": item_id,
            "drk_draft_path": review.drk_draft_path,
            "note": "DRK automatic Create Patient submission is intentionally not implemented.",
        }
        handoff_path.write_text(json.dumps(handoff, indent=2) + "\n", encoding="utf-8")
        self.store.mark_monday_applied(
            review_id,
            item_id=item_id,
            drk_status="pending_guarded_drk_execution",
        )
        entity_id = _workflow_entity_id(
            Path(review.canonical_path),
            fallback_digest=review.artifact_digest,
        )
        record_lifecycle_event(
            "monday_item_created",
            entity_id=entity_id,
            source="monday",
            event_key=f"monday-created:{review_id}:{item_id}",
            details={"review_id": review_id, "monday_item_id": item_id},
            patient_link=PatientLink(
                entity_id=entity_id,
                monday_item_id=item_id,
                patient_label=str(preview.get("item_name") or "") or None,
                updated_at=utc_now(),
            ),
        )
        record_lifecycle_event(
            "drk_handoff_created",
            entity_id=entity_id,
            source="drk",
            event_key=f"drk-handoff:{review_id}",
            details={"review_id": review_id, "status": "pending_guarded_drk_execution"},
        )
        return {
            "review_id": review_id,
            "status": "monday_applied_drk_pending",
            "monday_item_id": item_id,
            "drk_handoff_path": str(handoff_path),
        }


def artifact_digest(paths: Any) -> str:
    digest = hashlib.sha256()
    for path in sorted((Path(value) for value in paths), key=lambda item: item.name):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _artifact_paths(manifest: dict[str, Any]) -> dict[str, Path]:
    values = {
        "canonical": manifest.get("canonical_referral_path"),
        "plan": manifest.get("plan_path"),
        "monday": manifest.get("preview_path"),
        "drk": manifest.get("drk_draft_path"),
    }
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise ReviewWorkflowError(f"review artifacts are missing: {', '.join(missing)}")
    paths = {name: Path(str(value)).resolve() for name, value in values.items()}
    missing_files = [name for name, path in paths.items() if not path.is_file()]
    if missing_files:
        raise ReviewWorkflowError(f"review artifact files are missing: {', '.join(missing_files)}")
    return paths


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ReviewWorkflowError(f"expected a JSON object: {path}")
    return value


def _workflow_entity_id(canonical_path: Path, *, fallback_digest: str) -> str:
    canonical = _load_json(canonical_path)
    referral_id = str(canonical.get("referral_id") or "").strip()
    return referral_id or f"referral:{fallback_digest}"
