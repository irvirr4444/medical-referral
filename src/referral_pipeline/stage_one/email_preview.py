"""Render Stage 1 outbound emails without sending or persisting anything."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from referral_pipeline.review.summary import render_review_email
from referral_pipeline.stage_one.acknowledgement import render_partner_acknowledgement


def render_stage_one_email_preview(
    run_dir: str | Path,
    *,
    reviewer: str,
    write_config_path: str | Path,
) -> dict[str, Any]:
    manifests = list(Path(run_dir).resolve().rglob("manifest.json"))
    if len(manifests) != 1:
        raise ValueError(f"--run must contain exactly one manifest; found {len(manifests)}")
    manifest = _load(manifests[0])
    recipient = reviewer.strip()
    if not recipient:
        raise ValueError("an internal reviewer is required for email preview")

    review = render_review_email(
        review_id="preview_only",
        token="not-sent",
        canonical_path=_path(manifest, "canonical_referral_path"),
        intake_plan_path=_path(manifest, "plan_path"),
        monday_preview_path=_path(manifest, "preview_path"),
        drk_draft_path=_path(manifest, "drk_draft_path"),
        write_config_path=write_config_path,
        purpose="partner_contact",
    )
    acknowledgement_text, _ = render_partner_acknowledgement(manifest)
    return {
        "mode": "preview_only",
        "writes_performed": False,
        "messages_sent": False,
        "internal_review": {
            "recipient": recipient,
            "subject": review.subject,
            "text_body": review.text_body,
        },
        "partner_acknowledgement": {
            "recipient": str(manifest.get("source_sender") or "").strip() or None,
            "thread_message_id": str(manifest.get("source_message_id") or "").strip() or None,
            "text_body": acknowledgement_text,
        },
    }


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"manifest must be a JSON object: {path}")
    return value


def _path(manifest: dict[str, Any], key: str) -> Path:
    value = manifest.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"manifest is missing {key}")
    path = Path(value)
    if not path.is_file():
        raise ValueError(f"manifest path does not exist for {key}: {path}")
    return path
