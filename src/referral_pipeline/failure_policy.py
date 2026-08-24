"""Failure types and sender-notification policy for referral intake."""

from __future__ import annotations

from collections.abc import Iterator


class ReferralSubmissionError(ValueError):
    """A confirmed document problem that the referral sender can correct."""


def can_notify_referral_sender(error: Exception) -> bool:
    """Return true only for explicitly classified, sender-actionable failures."""
    return any(isinstance(exc, ReferralSubmissionError) for exc in _error_chain(error))


def _error_chain(error: Exception) -> Iterator[Exception]:
    current: BaseException | None = error
    seen: set[int] = set()
    while isinstance(current, Exception) and id(current) not in seen:
        seen.add(id(current))
        yield current
        current = current.__cause__ or current.__context__
