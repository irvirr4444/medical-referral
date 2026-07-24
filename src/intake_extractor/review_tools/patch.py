from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from ..models.review_schema import PredictionReview, ReviewIssue
from ..models.schema import ReferralIntake
from .targets import get_field_policy


IMMUTABLE_FIELDS = {
    "source_file",
    "pages_used",
}
PATCHABLE_FIELDS = set(ReferralIntake.model_fields) - IMMUTABLE_FIELDS

# Backward-compatible aliases used by existing tests / callers.
SENSITIVE_FIELDS = {"patient_name", "patient_dob", "insurance_id"}
FLEXIBLE_FIELDS = {
    "patient_address",
    "referring_facility",
    "referring_provider_name",
    "referring_phone",
    "referring_fax",
    "requested_services",
    "diagnosis_text",
    "referral_date",
}
DEFAULT_PATCH_THRESHOLD = 0.9
SENSITIVE_PATCH_THRESHOLD = 0.97
FLEXIBLE_PATCH_THRESHOLD = 0.8
MISSING_VALUE_BONUS = 0.05
REPLACEMENT_PENALTY = 0.03


@dataclass(frozen=True)
class AppliedPatch:
    field: str
    old_value: Any
    new_value: Any
    confidence: float
    reason: str


@dataclass(frozen=True)
class PatchDecision:
    field: str
    proposed_value: Any
    confidence: float
    evidence: str | None
    problem: str
    applied: bool
    reason: str


def apply_review_patches(
    candidate_json: dict[str, Any],
    review: PredictionReview,
    *,
    suspicious_fields: set[str] | None = None,
) -> tuple[dict[str, Any], list[AppliedPatch]]:
    updated, applied, _decisions = apply_review_patches_with_decisions(
        candidate_json,
        review,
        suspicious_fields=suspicious_fields,
    )
    return updated, applied


def apply_review_patches_with_decisions(
    candidate_json: dict[str, Any],
    review: PredictionReview,
    *,
    suspicious_fields: set[str] | None = None,
) -> tuple[dict[str, Any], list[AppliedPatch], list[PatchDecision]]:
    flagged = suspicious_fields or set()
    validated_candidate = ReferralIntake.model_validate(candidate_json).model_dump(mode="json")
    updated = deepcopy(validated_candidate)
    applied: list[AppliedPatch] = []
    decisions: list[PatchDecision] = []

    for issue in review.issues:
        current_value = updated.get(issue.field)
        allowed, gate_reason = explain_review_issue_gate(issue, current_value, suspicious_fields=flagged)
        if not allowed:
            if issue.suggest_patch or issue.field in PATCHABLE_FIELDS:
                decisions.append(
                    PatchDecision(
                        field=issue.field,
                        proposed_value=issue.proposed_value,
                        confidence=issue.confidence,
                        evidence=issue.evidence,
                        problem=issue.problem,
                        applied=False,
                        reason=gate_reason,
                    )
                )
            continue

        proposed_value = issue.proposed_value
        if _values_equivalent(current_value, proposed_value):
            decisions.append(
                PatchDecision(
                    field=issue.field,
                    proposed_value=proposed_value,
                    confidence=issue.confidence,
                    evidence=issue.evidence,
                    problem=issue.problem,
                    applied=False,
                    reason="proposed value equivalent to current value",
                )
            )
            continue

        trial = deepcopy(updated)
        trial[issue.field] = proposed_value
        try:
            validated_trial = ReferralIntake.model_validate(trial)
        except ValidationError as exc:
            decisions.append(
                PatchDecision(
                    field=issue.field,
                    proposed_value=proposed_value,
                    confidence=issue.confidence,
                    evidence=issue.evidence,
                    problem=issue.problem,
                    applied=False,
                    reason=f"schema validation failed: {exc.error_count()} error(s)",
                )
            )
            continue

        updated = validated_trial.model_dump(mode="json")
        applied.append(
            AppliedPatch(
                field=issue.field,
                old_value=current_value,
                new_value=proposed_value,
                confidence=issue.confidence,
                reason=issue.problem,
            )
        )
        decisions.append(
            PatchDecision(
                field=issue.field,
                proposed_value=proposed_value,
                confidence=issue.confidence,
                evidence=issue.evidence,
                problem=issue.problem,
                applied=True,
                reason="applied",
            )
        )

    return updated, applied, decisions


def should_apply_review_issue(
    issue: ReviewIssue,
    current_value: Any,
    *,
    suspicious_fields: set[str] | None = None,
) -> bool:
    allowed, _reason = explain_review_issue_gate(
        issue,
        current_value,
        suspicious_fields=suspicious_fields,
    )
    return allowed


def explain_review_issue_gate(
    issue: ReviewIssue,
    current_value: Any,
    *,
    suspicious_fields: set[str] | None = None,
) -> tuple[bool, str]:
    if issue.field not in PATCHABLE_FIELDS:
        return False, f"field '{issue.field}' is not patchable"
    if not issue.suggest_patch:
        return False, "suggest_patch is false"
    if "proposed_value" not in issue.model_fields_set:
        return False, "proposed_value was omitted"
    threshold = patch_confidence_threshold(
        issue.field,
        current_value,
        suspicious_fields=suspicious_fields,
    )
    if issue.confidence < threshold:
        return (
            False,
            f"confidence {issue.confidence:.2f} below threshold {threshold:.2f} for {issue.field}",
        )
    return True, "passed patch gates"


def patch_confidence_threshold(
    field: str,
    current_value: Any,
    *,
    suspicious_fields: set[str] | None = None,
) -> float:
    policy = get_field_policy(field)
    threshold = policy.base_threshold
    flagged = suspicious_fields or set()

    if _is_missing_value(current_value):
        threshold -= MISSING_VALUE_BONUS
    elif policy.replacement_penalty:
        threshold += policy.replacement_penalty

    if field in flagged:
        threshold -= policy.suspicious_bonus

    return max(policy.min_threshold, min(0.99, threshold))


def _is_missing_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, list):
        return len(value) == 0
    return False


def _values_equivalent(left: Any, right: Any) -> bool:
    return _stable_json(left) == _stable_json(right)


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)

