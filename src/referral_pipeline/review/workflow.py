"""Create review requests and execute strictly confirmed destination writes."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from Outlook.review_mail import OutlookReviewMailbox
from referral_pipeline.review.contact_outcome import classify_partner_contact
from referral_pipeline.review.intent import IntentResult, classify_reply_intent
from referral_pipeline.review.store import build_review_store
from referral_pipeline.review.summary import render_review_email
from referral_pipeline.monitoring.models import PatientLink, utc_now
from referral_pipeline.monitoring.observer import record_lifecycle_event
from referral_pipeline.monitoring.store import WorkflowStore
from referral_pipeline.persistence_policy import SyntheticPersistencePolicy
from referral_pipeline.stage_one.tracker import StageOneTracker
from referral_pipeline.workflow import WorkflowExecutionService


class ReviewWorkflowError(RuntimeError):
    pass


def create_and_send_review(
    manifest: dict[str, Any],
    *,
    recipient: str,
    write_config_path: str | Path,
    state_db: str | Path,
    mailbox: OutlookReviewMailbox,
    purpose: str = "destination_write",
    workflow_case_id: str | None = None,
) -> dict[str, Any]:
    recipient = recipient.strip()
    if not recipient:
        raise ReviewWorkflowError("review recipient cannot be empty")
    source_message_id = str(manifest.get("source_message_id") or "").strip()
    if not source_message_id:
        raise ReviewWorkflowError("source message ID is required to send the review as a reply")
    source_conversation_id = str(manifest.get("source_conversation_id") or "").strip()
    if not source_conversation_id:
        raise ReviewWorkflowError("source conversation ID is required for human-readable confirmation")
    paths = _artifact_paths(manifest)
    snapshots = {
        "canonical": _load_json(paths["canonical"]),
        "plan": _load_json(paths["plan"]),
        "monday": _load_json(paths["monday"]),
        "drk": _load_json(paths["drk"]),
    }
    digest = artifact_payload_digest(snapshots)
    entity_id = _workflow_entity_id(paths["canonical"], fallback_digest=digest)
    remote_persistence_allowed = SyntheticPersistencePolicy.from_environment().permits(
        str(manifest.get("attachment_sha256") or "") or None
    )
    store = build_review_store(state_db, allow_supabase=remote_persistence_allowed)
    existing = store.find_active(
        artifact_digest=digest,
        source_message_id=source_message_id,
        recipient=recipient,
        purpose=purpose,
    )
    if existing is not None and (existing.email_html_body or existing.email_text_body or existing.email_body):
        subject = existing.email_subject or f"[WCW REFERRAL REVIEW] {existing.review_id}"
        content_type = (existing.email_content_type or ("HTML" if existing.email_html_body else "Text")).upper()
        html_body = existing.email_html_body
        text_body = existing.email_text_body or existing.email_body
        body_for_send = html_body if content_type == "HTML" and html_body else text_body
        review_id = existing.review_id
        review_status = (
            "awaiting_confirmation"
            if existing.status in {"awaiting_confirmation", "review_send_failed"}
            else existing.status
        )
        if review_status == "review_send_failed":
            review_status = "awaiting_confirmation"
        try:
            mailbox.send_reply(
                source_message_id=source_message_id,
                recipient=recipient,
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
            allow_remote_persistence=remote_persistence_allowed,
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
            purpose=purpose,
        )
        return {
            "review_id": review_id,
            "review_status": review_status,
            "review_recipient": recipient,
            "review_audit_path": str(audit_path),
            "review_reused": True,
            "review_content_type": content_type,
            "review_purpose": purpose,
        }

    review_id = f"review_{digest[:12]}_{secrets.token_hex(3)}"
    token = secrets.token_urlsafe(18)
    preview = snapshots["monday"]
    approval_allowed = purpose == "partner_contact" or not bool(preview.get("blocked"))
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
        purpose=purpose,
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
        source_conversation_id=source_conversation_id,
        source_attachment_sha256=str(manifest.get("attachment_sha256") or "") or None,
        canonical_referral=snapshots["canonical"],
        intake_plan=snapshots["plan"],
        monday_preview=snapshots["monday"],
        drk_draft=snapshots["drk"],
        status=review_status,
        purpose=purpose,
        workflow_case_id=workflow_case_id,
        email_subject=email.subject,
        email_html_body=email.html_body,
        email_text_body=email.text_body,
        email_content_type=email.content_type,
    )
    try:
        mailbox.send_reply(
            source_message_id=source_message_id,
            recipient=recipient,
            html_body=email.html_body,
            text_body=email.text_body,
            content_type=email.content_type,
        )
    except Exception as error:
        store.mark_failed(review_id, error=f"review email send failed: {error}", status="review_send_failed")
        raise
    store.mark_sent(
        review_id,
        status=review_status,
        email_subject=email.subject,
        email_html_body=email.html_body,
        email_text_body=email.text_body,
        email_content_type=email.content_type,
    )

    record_lifecycle_event(
        "review_requested",
        entity_id=entity_id,
        source="outlook",
        event_key=f"review-requested:{review_id}",
        details={"review_id": review_id, "recipient": recipient, "status": review_status, "reused": False},
        allow_remote_persistence=remote_persistence_allowed,
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
        purpose=purpose,
    )
    return {
        "review_id": review_id,
        "review_status": review_status,
        "review_recipient": recipient,
        "review_audit_path": str(audit_path),
        "review_reused": False,
        "review_content_type": email.content_type,
        "review_purpose": purpose,
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
    purpose: str,
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
                "purpose": purpose,
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
    def __init__(
        self,
        *,
        state_db: str | Path,
        mailbox: OutlookReviewMailbox,
        intent_classifier: Callable[[str], IntentResult] = classify_reply_intent,
        workflow_store: WorkflowStore | None = None,
    ) -> None:
        self.state_db = Path(state_db)
        self.store = build_review_store(state_db)
        self.mailbox = mailbox
        self.intent_classifier = intent_classifier
        self.workflow_store = workflow_store

    def poll(
        self,
        *,
        max_messages: int = 25,
        execute: bool = False,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        if execute and dry_run:
            raise ReviewWorkflowError("execute and dry_run modes are mutually exclusive")
        accepted: list[str] = []
        partner_contacts: list[str] = []
        partner_contact_outcomes: list[dict[str, str]] = []
        corrections: list[str] = []
        unclear: list[str] = []
        duplicates: list[str] = []
        ignored: list[dict[str, str]] = []
        for reply in self.mailbox.list_replies(max_messages=max_messages):
            if self.store.response_exists(reply.message_id):
                duplicates.append(reply.message_id)
                continue
            conversation_id = (reply.conversation_id or "").strip()
            if not conversation_id:
                ignored.append({"message_id": reply.message_id, "reason": "missing_conversation_id"})
                continue
            review = self.store.find_confirmable_for_reply(
                sender=reply.sender,
                conversation_id=conversation_id,
            )
            if review is None:
                continue
            if reply.message_id == review.source_message_id or not _reply_is_after_review(
                reply.received_at,
                review.created_at,
            ):
                ignored.append(
                    {
                        "message_id": reply.message_id,
                        "reason": "message_predates_review_request",
                    }
                )
                continue

            contact = (
                classify_partner_contact(
                    reply.text,
                    intent_classifier=self.intent_classifier,
                )
                if review.purpose == "partner_contact"
                else None
            )
            intent = contact.intent if contact is not None else self.intent_classifier(reply.text)
            response_result = self.store.process_response(
                review_id=review.review_id,
                message_id=reply.message_id,
                sender=reply.sender,
                conversation_id=conversation_id,
                received_at=reply.received_at,
                text=reply.text,
                intent=intent.intent,
                classifier_source=intent.source,
                classifier_reason=intent.reason,
            )
            if response_result == "duplicate":
                duplicates.append(reply.message_id)
                continue
            if response_result in {"confirmed", "partner_contact_confirmed"}:
                if response_result == "partner_contact_confirmed":
                    partner_contacts.append(review.review_id)
                    partner_contact_outcomes.append(
                        {
                            "review_id": review.review_id,
                            "outcome": contact.outcome if contact is not None else "reached",
                        }
                    )
                    if self.workflow_store is not None and review.workflow_case_id:
                        completed_case = StageOneTracker(
                            self.workflow_store
                        ).partner_contact_confirmed(
                            review.workflow_case_id,
                            confirmed_by=reply.sender,
                            message_id=reply.message_id,
                            outcome=contact.outcome if contact is not None else "reached",
                        )
                        if completed_case is not None:
                            WorkflowExecutionService(self.workflow_store).start_assignment(
                                completed_case.case_id,
                                contact_outcome=(
                                    contact.outcome if contact is not None else "reached"
                                ),
                            )
                else:
                    accepted.append(review.review_id)
                record_lifecycle_event(
                    (
                        "partner_contact_confirmed"
                        if response_result == "partner_contact_confirmed"
                        else "review_confirmed"
                    ),
                    entity_id=_workflow_entity_id(
                        Path(review.canonical_path),
                        fallback_digest=review.artifact_digest,
                    ),
                    source="outlook",
                    event_key=f"review-confirmed:{reply.message_id}",
                    details={
                        "review_id": review.review_id,
                        "confirmation_message_id": reply.message_id,
                        **(
                            {"contact_outcome": contact.outcome}
                            if contact is not None and contact.outcome is not None
                            else {}
                        ),
                    },
                    allow_remote_persistence=_review_allows_remote_persistence(review),
                )
            elif response_result == "needs_correction":
                corrections.append(review.review_id)
            elif response_result == "unclear":
                unclear.append(review.review_id)
                ignored.append(
                    {
                        "message_id": reply.message_id,
                        "reason": f"intent_{intent.intent}:{intent.reason}",
                    }
                )
            else:
                ignored.append(
                    {"message_id": reply.message_id, "reason": response_result}
                )

        applied: list[dict[str, Any]] = []
        if dry_run or execute:
            for review in self.store.confirmed():
                if dry_run and review.status == "dry_run_completed":
                    continue
                try:
                    if dry_run:
                        applied.append(self._dry_run(review.review_id))
                    else:
                        applied.append(self._execute(review.review_id))
                except Exception as error:
                    if dry_run:
                        self.store.record_dry_run_failure(
                            review.review_id,
                            error=str(error),
                        )
                    else:
                        self.store.mark_failed(review.review_id, error=str(error))
                    applied.append(
                        {
                            "review_id": review.review_id,
                            "status": "failed",
                            "error": str(error),
                            "writes_performed": False,
                        }
                    )
        return {
            "mode": "execute" if execute else ("dry_run" if dry_run else "check_only"),
            "writes_attempted": bool(execute),
            "accepted_confirmations": accepted,
            "partner_contact_confirmations": partner_contacts,
            "partner_contact_outcomes": partner_contact_outcomes,
            "correction_or_denial_reviews": corrections,
            "unclear_reviews": unclear,
            "duplicate_response_messages": duplicates,
            "ignored_confirmations": ignored,
            "executed": applied,
        }

    def _dry_run(self, review_id: str) -> dict[str, Any]:
        review = self.store.get(review_id)
        snapshots = _review_snapshots(review)
        _assert_digest(review, snapshots)
        if not os.getenv("MONDAY_DOT_COM_API_KEY", "").strip():
            raise ReviewWorkflowError("MONDAY_DOT_COM_API_KEY is required for Monday execution")
        preview = snapshots["monday"]
        drk = snapshots["drk"]
        if preview.get("blocked"):
            raise ReviewWorkflowError(
                "confirmed Monday preview is blocked: "
                + ", ".join(str(item) for item in preview.get("blockers") or [])
            )
        missing_monday = [
            field
            for field in ("board_id", "group_id", "item_name", "column_values", "operation")
            if field not in preview
        ]
        if missing_monday:
            raise ReviewWorkflowError(
                f"Monday preview is incomplete: missing {', '.join(missing_monday)}"
            )
        if preview.get("operation") != "create_item":
            raise ReviewWorkflowError("Monday preview operation must be create_item")

        result = {
            "review_id": review_id,
            "status": "dry_run_completed",
            "writes_performed": False,
            "monday": {
                "would_create": True,
                "blocked": False,
                "board_id": preview.get("board_id"),
                "group_id": preview.get("group_id"),
                "item_name": preview.get("item_name"),
                "source": "supabase" if review.monday_preview is not None else review.monday_preview_path,
                "written": False,
            },
            "drk": {
                "would_prepare_patient": True,
                "ready_for_fill": bool(drk.get("ready_for_fill")),
                "blockers": list(drk.get("blockers") or []),
                "source": "supabase" if review.drk_draft is not None else review.drk_draft_path,
                "written": False,
                "status": "pending_draft",
                "note": "DRK Create Patient submission is intentionally unfinished.",
            },
            "note": "Dry run only. No data was written to Monday or DRK.",
        }
        self.store.record_dry_run(review_id, result=result)
        output_dir = _approval_output_dir(review, self.state_db)
        result_path = output_dir / "approval-dry-run.json"
        result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self.mailbox.send_reply(
            source_message_id=review.source_message_id,
            recipient=review.recipient,
            content_type="HTML",
            html_body=(
                "<p><strong>Confirmation received.</strong></p>"
                "<p>The Monday and DRK workflow dry run completed successfully. "
                "No patient data was created or changed. DRK remains a pending draft.</p>"
            ),
            text_body=(
                "Confirmation received.\n\n"
                "The Monday and DRK workflow dry run completed successfully. "
                "No patient data was created or changed. DRK remains a pending draft.\n"
            ),
        )
        return {
            "review_id": review_id,
            "status": "dry_run_completed",
            "writes_performed": False,
            "dry_run_path": str(result_path),
        }

    def _execute(self, review_id: str) -> dict[str, Any]:
        claim = self.store.claim_for_monday_execution(review_id)
        if claim == "already_applied":
            review = self.store.get(review_id)
            return {
                "review_id": review_id,
                "status": "monday_applied_drk_pending",
                "writes_performed": False,
                "monday_item_id": review.monday_item_id,
                "note": "Monday item was already created; DRK remains pending.",
            }
        if claim != "claimed":
            raise ReviewWorkflowError(f"unable to claim review for Monday execution: {claim}")

        review = self.store.get(review_id)
        snapshots = _review_snapshots(review)
        _assert_digest(review, snapshots)
        preview = snapshots["monday"]
        if preview.get("blocked"):
            raise ReviewWorkflowError("confirmed Monday preview is blocked")

        from master_sheet_writer import apply_master_sheet_create

        try:
            applied = apply_master_sheet_create(
                preview,
                on_item_created=lambda item: self.store.mark_monday_item_created(
                    review_id,
                    item_id=str(item["id"]),
                ),
            )
        except Exception as error:
            current = self.store.get(review_id)
            if current.monday_item_id:
                self.store.mark_monday_applied(
                    review_id,
                    item_id=current.monday_item_id,
                    drk_status="pending_draft",
                )
                return {
                    "review_id": review_id,
                    "status": "monday_applied_drk_pending",
                    "writes_performed": True,
                    "monday_item_id": current.monday_item_id,
                    "post_create_error": str(error),
                    "note": (
                        "Monday item creation succeeded and its ID was persisted, "
                        "but a post-create action failed. DRK remains pending."
                    ),
                }
            raise
        item_id = str(applied["item"]["id"])
        self.store.mark_monday_applied(
            review_id,
            item_id=item_id,
            drk_status="pending_draft",
        )
        output_dir = _approval_output_dir(review, self.state_db)
        result = {
            "review_id": review_id,
            "status": "monday_applied_drk_pending",
            "writes_performed": True,
            "monday": {
                "created": True,
                "item_id": item_id,
                "applied_actions": applied.get("applied_actions") or [],
            },
            "drk": {
                "created": False,
                "status": "pending_draft",
                "note": "DRK Create Patient submission is intentionally unfinished.",
            },
        }
        result_path = output_dir / "approval-execute-result.json"
        result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self.mailbox.send_reply(
            source_message_id=review.source_message_id,
            recipient=review.recipient,
            content_type="HTML",
            html_body=(
                "<p><strong>Confirmation received.</strong></p>"
                f"<p>The patient was created in Monday.com (item {item_id}). "
                "DRK remains a pending draft and was not submitted.</p>"
            ),
            text_body=(
                "Confirmation received.\n\n"
                f"The patient was created in Monday.com (item {item_id}). "
                "DRK remains a pending draft and was not submitted.\n"
            ),
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
            allow_remote_persistence=_review_allows_remote_persistence(review),
        )
        record_lifecycle_event(
            "drk_handoff_created",
            entity_id=entity_id,
            source="drk",
            event_key=f"drk-handoff:{review_id}",
            details={"review_id": review_id, "status": "pending_guarded_drk_execution"},
            allow_remote_persistence=_review_allows_remote_persistence(review),
        )
        return {
            "review_id": review_id,
            "status": "monday_applied_drk_pending",
            "writes_performed": True,
            "monday_item_id": item_id,
            "result_path": str(result_path),
        }

    def _apply(self, review_id: str) -> dict[str, Any]:
        """Backward-compatible alias used by older tests; dry-run only. """
        return self._dry_run(review_id)


def artifact_digest(paths: Any) -> str:
    digest = hashlib.sha256()
    for path in sorted((Path(value) for value in paths), key=lambda item: item.name):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _review_allows_remote_persistence(review: Any) -> bool:
    return SyntheticPersistencePolicy.from_environment().permits(
        getattr(review, "source_attachment_sha256", None)
    )


def artifact_payload_digest(snapshots: dict[str, dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for name in ("canonical", "plan", "monday", "drk"):
        value = snapshots[name]
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(
            json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
                "utf-8"
            )
        )
        digest.update(b"\0")
    return digest.hexdigest()


def _assert_digest(review: Any, snapshots: dict[str, dict[str, Any]]) -> None:
    if review.monday_preview is not None:
        actual_digest = artifact_payload_digest(snapshots)
    else:
        actual_digest = artifact_digest(
            [
                Path(review.canonical_path),
                Path(review.intake_plan_path),
                Path(review.monday_preview_path),
                Path(review.drk_draft_path),
            ]
        )
    if actual_digest != review.artifact_digest:
        raise ReviewWorkflowError("approved artifacts changed after the review email was sent")


def _approval_output_dir(review: Any, state_db: Path) -> Path:
    if review.monday_preview_path:
        output_dir = Path(review.monday_preview_path).parent
    else:
        output_dir = state_db.parent / "approval-results" / review.review_id
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _review_snapshots(review: Any) -> dict[str, dict[str, Any]]:
    stored = {
        "canonical": review.canonical_referral,
        "plan": review.intake_plan,
        "monday": review.monday_preview,
        "drk": review.drk_draft,
    }
    if all(isinstance(value, dict) for value in stored.values()):
        return stored
    paths = {
        "canonical": review.canonical_path,
        "plan": review.intake_plan_path,
        "monday": review.monday_preview_path,
        "drk": review.drk_draft_path,
    }
    if not all(paths.values()):
        raise ReviewWorkflowError("review artifacts are unavailable")
    return {name: _load_json(Path(path)) for name, path in paths.items()}


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


def _reply_is_after_review(received_at: str | None, review_created_at: str) -> bool:
    if not received_at:
        return False
    try:
        received = datetime.fromisoformat(received_at.replace("Z", "+00:00"))
        created = datetime.fromisoformat(review_created_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    return received > created


def _workflow_entity_id(canonical_path: Path, *, fallback_digest: str) -> str:
    canonical = _load_json(canonical_path)
    referral_id = str(canonical.get("referral_id") or "").strip()
    return referral_id or f"referral:{fallback_digest}"
