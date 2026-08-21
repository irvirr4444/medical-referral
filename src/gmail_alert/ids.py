"""Gmail alert action IDs — product email set (decide + notify).

Not every Stage Ops confirmation timer gets an email. Monday-driven and
auto-assign/select paths are silent; this catalog is only what humans read.
"""

from __future__ import annotations

from typing import Literal, get_args

ConfirmationActionId = Literal[
    "confirm-intake-review",
    "confirm-partner-contacted",
    "cm-assigned",
    "use-fallback-provider",
    "no-area-provider",
    "send-referral-provider",
    "eod-follow-up-cm",
    "eod-escalate",
    "not-seen-week-1",
    "not-seen-week-2",
    "not-seen-week-3",
]

AlertKind = Literal["decide", "notify"]

RecipientRole = Literal[
    "intake_lead",
    "assigned_cm",
    "provider",
    "scheduling_lead",
    "management",
]

ACTION_IDS: tuple[ConfirmationActionId, ...] = get_args(ConfirmationActionId)
