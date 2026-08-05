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
    paths = _artifact_paths(manifest)
    digest = artifact_digest(paths.values())
    review_id = f"review_{digest[:12]}_{secrets.token_hex(3)}"
    token = secrets.token_urlsafe(18)
    preview = _load_json(paths["monday"])
    approval_allowed = not bool(preview.get("blocked"))
    review_status = "awaiting_confirmation" if approval_allowed else "needs_correction"
    subject, body = render_review_email(
        review_id=review_id,
        token=token,
        canonical_path=paths["canonical"],
        intake_plan_path=paths["plan"],
        monday_preview_path=paths["monday"],
        drk_draft_path=paths["drk"],
        write_config_path=write_config_path,
        approval_allowed=approval_allowed,
    )
    store = ReviewStore(state_db)
    store.add(
        review_id=review_id,
        token=token,
        recipient=recipient,
        artifact_digest=digest,
        canonical_path=str(paths["canonical"].resolve()),
        intake_plan_path=str(paths["plan"].resolve()),
        monday_preview_path=str(paths["monday"].resolve()),
        drk_draft_path=str(paths["drk"].resolve()),
        source_message_id=str(manifest.get("source_message_id") or ""),
        status=review_status,
    )
    try:
        mailbox.send(recipient=recipient, subject=subject, text_body=body)
    except Exception as error:
        store.mark_failed(review_id, error=f"review email send failed: {error}", status="review_send_failed")
        raise

    audit_path = paths["monday"].parent / "review-request.json"
    email_path = paths["monday"].parent / "review-email.txt"
    email_path.write_text(body, encoding="utf-8")
    audit_path.write_text(
        json.dumps(
            {
                "review_id": review_id,
                "recipient": recipient,
                "status": review_status,
                "artifact_digest": digest,
                "subject": subject,
                "email_path": str(email_path),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "review_id": review_id,
        "review_status": review_status,
        "review_recipient": recipient,
        "review_audit_path": str(audit_path),
    }


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
