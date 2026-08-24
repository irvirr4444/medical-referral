from __future__ import annotations

import pytest

from referral_pipeline.review.contact_outcome import classify_partner_contact
from referral_pipeline.review.intent import IntentResult


@pytest.mark.parametrize(
    ("reply", "outcome"),
    [
        ("Reached the referral partner", "reached"),
        ("No answer, left voicemail", "not_reached"),
        ("Information still missing: insurance card", "information_still_missing"),
    ],
)
def test_explicit_partner_contact_outcomes_are_local_confirmations(reply, outcome) -> None:
    result = classify_partner_contact(
        reply,
        intent_classifier=lambda _text: (_ for _ in ()).throw(AssertionError()),
    )

    assert result.outcome == outcome
    assert result.intent.intent == "confirm"
    assert result.intent.source == "local"


def test_ambiguous_partner_contact_reply_stays_fail_closed() -> None:
    result = classify_partner_contact(
        "I will try later",
        intent_classifier=lambda _text: IntentResult("unclear", "ambiguous", "test"),
    )

    assert result.outcome is None
    assert result.intent.intent == "unclear"


def test_plain_confirmation_preserves_existing_reached_behavior() -> None:
    result = classify_partner_contact(
        "Confirmed",
        intent_classifier=lambda _text: IntentResult("confirm", "explicit", "local"),
    )

    assert result.outcome == "reached"
