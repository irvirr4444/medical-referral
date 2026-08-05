"""Strict confirmation parser used by the current simulated review flow."""

from __future__ import annotations

import re

from referral_pipeline.review.models import ApprovalCommand


COMMAND = re.compile(r"^\s*CONFIRMED\s+(review_[a-z0-9_-]+)\s+([A-Za-z0-9_-]{16,})\s*$", re.IGNORECASE)


def parse_approval_command(text: str) -> ApprovalCommand | None:
    """Accept one standalone command line; quoted instructions cannot authorize."""
    matches = [match for line in text.splitlines() if (match := COMMAND.fullmatch(line))]
    if len(matches) != 1:
        return None
    return ApprovalCommand(review_id=matches[0].group(1), token=matches[0].group(2))
