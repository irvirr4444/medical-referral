"""File-based audit artifacts for the second-pass reviewer."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ..models.review_schema import PredictionReview
from .patch import PatchDecision
from .signals import FieldSignal


@dataclass(frozen=True)
class AuditDocument:
    source_file: str
    overall_verdict: str
    summary: str
    reviewed_fields: list[str]
    suspicious_fields: list[str]
    field_checks: list[dict[str, Any]]
    decisions: list[dict[str, Any]]
    applied_count: int
    rejected_count: int


def build_document_audit(
    *,
    source_file: str,
    candidate: dict[str, Any],
    review: PredictionReview,
    decisions: list[PatchDecision],
    signals: list[FieldSignal],
    reviewed_fields: list[str],
) -> AuditDocument:
    decision_rows: list[dict[str, Any]] = []
    for decision in decisions:
        decision_rows.append(
            {
                "field": decision.field,
                "original_value": candidate.get(decision.field),
                "proposed_value": decision.proposed_value,
                "confidence": decision.confidence,
                "evidence": decision.evidence,
                "problem": decision.problem,
                "applied": decision.applied,
                "reason": decision.reason,
            }
        )

    # Include suggest_patch=false issues that never entered the decision list.
    decided_fields = {row["field"] for row in decision_rows}
    for issue in review.issues:
        if issue.field in decided_fields:
            continue
        decision_rows.append(
            {
                "field": issue.field,
                "original_value": candidate.get(issue.field, issue.predicted_value),
                "proposed_value": issue.proposed_value if issue.suggest_patch else None,
                "confidence": issue.confidence,
                "evidence": issue.evidence,
                "problem": issue.problem,
                "applied": False,
                "reason": "issue reported without an accepted patch proposal"
                if not issue.suggest_patch
                else "issue not processed by patch gate",
            }
        )

    field_checks = [{"field": check.field, "status": check.status, "note": check.note} for check in review.field_checks]
    applied_count = sum(1 for row in decision_rows if row["applied"])
    rejected_count = sum(1 for row in decision_rows if not row["applied"])
    return AuditDocument(
        source_file=source_file,
        overall_verdict=review.overall_verdict,
        summary=review.summary,
        reviewed_fields=list(reviewed_fields),
        suspicious_fields=sorted({signal.field for signal in signals}),
        field_checks=field_checks,
        decisions=decision_rows,
        applied_count=applied_count,
        rejected_count=rejected_count,
    )


def write_document_audit(audit_dir: Path, stem: str, review: PredictionReview, audit: AuditDocument) -> None:
    audit_dir.mkdir(parents=True, exist_ok=True)
    (audit_dir / f"{stem}.review.json").write_text(
        json.dumps(review.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    applied = [row for row in audit.decisions if row["applied"]]
    (audit_dir / f"{stem}.applied_patches.json").write_text(
        json.dumps(applied, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (audit_dir / f"{stem}.audit.json").write_text(
        json.dumps(asdict(audit), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def write_folder_audit_summary(audit_dir: Path, audits: list[AuditDocument]) -> None:
    audit_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "documents": len(audits),
        "total_applied_patches": sum(item.applied_count for item in audits),
        "total_rejected_patches": sum(item.rejected_count for item in audits),
        "documents_with_applied_patches": sum(1 for item in audits if item.applied_count),
        "by_document": [
            {
                "source_file": item.source_file,
                "overall_verdict": item.overall_verdict,
                "applied_count": item.applied_count,
                "rejected_count": item.rejected_count,
                "suspicious_fields": item.suspicious_fields,
                "applied_fields": sorted({row["field"] for row in item.decisions if row["applied"]}),
            }
            for item in audits
        ],
    }
    (audit_dir / "audit_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    rows: list[dict[str, Any]] = []
    for item in audits:
        if not item.decisions:
            rows.append(
                {
                    "source_file": item.source_file,
                    "field": "",
                    "applied": "",
                    "confidence": "",
                    "reason": "no issues/patches",
                    "evidence": "",
                    "original_value": "",
                    "proposed_value": "",
                }
            )
            continue
        for decision in item.decisions:
            rows.append(
                {
                    "source_file": item.source_file,
                    "field": decision["field"],
                    "applied": decision["applied"],
                    "confidence": decision["confidence"],
                    "reason": decision["reason"],
                    "evidence": decision.get("evidence") or "",
                    "original_value": json.dumps(decision["original_value"], ensure_ascii=False, sort_keys=True),
                    "proposed_value": json.dumps(decision["proposed_value"], ensure_ascii=False, sort_keys=True),
                }
            )

    path = audit_dir / "audit_summary.csv"
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

