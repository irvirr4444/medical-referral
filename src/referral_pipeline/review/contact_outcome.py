"""Normalize Stage 1 referral-partner outreach replies."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from referral_pipeline.review.intent import IntentResult, classify_reply_intent


_OUTCOMES = (
    (
        "not_reached",
        re.compile(
            r"^\s*(?:no answer|not reached|unreachable|could not reach|unable to reach|"
            r"left (?:a )?(?:voice)?mail|left a message)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "information_still_missing",
        re.compile(
            r"^\s*(?:information (?:is )?still missing|still missing|unable to obtain|"
            r"awaiting (?:information|documents?))\b",
            re.IGNORECASE,
        ),
    ),
    (
        "reached",
        re.compile(
            r"^\s*(?:reached|contacted|spoke (?:with|to)|confirmed with)\b",
            re.IGNORECASE,
        ),
    ),
)


@dataclass(frozen=True)
class PartnerContactResult:
    outcome: str | None
    intent: IntentResult


def classify_partner_contact(
    text: str,
    *,
    intent_classifier: Callable[[str], IntentResult] = classify_reply_intent,
) -> PartnerContactResult:
    """Recognize explicit outreach outcomes; ambiguous replies stay fail-closed."""
    reply = " ".join((text or "").split()).strip()
    for outcome, pattern in _OUTCOMES:
        if pattern.match(reply):
            return PartnerContactResult(
                outcome=outcome,
                intent=IntentResult(
                    intent="confirm",
                    reason=f"explicit partner contact outcome: {outcome}",
                    source="local",
                ),
            )

    intent = intent_classifier(reply)
    return PartnerContactResult(
        outcome="reached" if intent.intent == "confirm" else None,
        intent=intent,
    )
