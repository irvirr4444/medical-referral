"""Case-specific recipient emails for demo seeds (not env role lists)."""

from __future__ import annotations

from gmail_alert.ids import ConfirmationActionId, RecipientRole

# Demo addresses — live runs pass real case emails on AlertContext.
_CASE_EMAILS: dict[ConfirmationActionId, dict[RecipientRole, tuple[str, ...]]] = {
    "confirm-intake-review": {"intake_lead": ("intake@westcoastwound.com",)},
    "confirm-partner-contacted": {"intake_lead": ("intake@westcoastwound.com",)},
    "cm-assigned": {"assigned_cm": ("cwinfield@westcoastwound.com",)},
    "use-fallback-provider": {"assigned_cm": ("druiz@westcoastwound.com",)},
    "no-area-provider": {
        "management": ("nchorvat@westcoastwound.com",),
        "assigned_cm": ("nchorvat@westcoastwound.com",),
    },
    "send-referral-provider": {
        "provider": ("daniel.rowady@example.com",),
        "assigned_cm": ("druiz@westcoastwound.com",),
    },
    "eod-follow-up-cm": {"assigned_cm": ("druiz@westcoastwound.com",)},
    "eod-escalate": {
        "management": ("nchorvat@westcoastwound.com",),
        "scheduling_lead": ("sched@westcoastwound.com",),
    },
    "not-seen-week-1": {"assigned_cm": ("cwinfield@westcoastwound.com",)},
    "not-seen-week-2": {"assigned_cm": ("cwinfield@westcoastwound.com",)},
    "not-seen-week-3": {
        "management": ("nchorvat@westcoastwound.com",),
        "assigned_cm": ("nchorvat@westcoastwound.com",),
    },
}


def case_emails_for(action_id: ConfirmationActionId) -> dict[RecipientRole, tuple[str, ...]]:
    return dict(_CASE_EMAILS[action_id])
