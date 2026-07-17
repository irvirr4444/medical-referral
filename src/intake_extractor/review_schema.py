from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ReviewIssue(BaseModel):
    field: str
    severity: Literal["minor", "major"]
    predicted_value: Any = None
    suggest_patch: bool = False
    proposed_value: Any = None
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    expected_value: str | None = None
    problem: str
    evidence: str | None = None


class FieldCheck(BaseModel):
    """Forced per-field checklist entry for targeted second-pass review."""

    field: str
    status: Literal["ok", "issue", "uncertain"]
    note: str | None = None


class PredictionReview(BaseModel):
    source_file: str | None = None
    overall_verdict: Literal["pass", "minor_issues", "major_issues"]
    summary: str
    correct_highlights: list[str] = Field(default_factory=list)
    field_checks: list[FieldCheck] = Field(default_factory=list)
    issues: list[ReviewIssue] = Field(default_factory=list)
