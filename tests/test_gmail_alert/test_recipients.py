from __future__ import annotations

import pytest

from gmail_alert.recipients import GmailAlertConfigError, parse_address_list, resolve_recipients


def test_parse_address_list() -> None:
    assert parse_address_list(" a@x.com , b@x.com ") == ("a@x.com", "b@x.com")
    assert parse_address_list("") == ()
    assert parse_address_list(None) == ()


def test_resolve_from_case_emails() -> None:
    to, cc = resolve_recipients(
        ("assigned_cm",),
        ("scheduling_lead",),
        case_emails={
            "assigned_cm": ("cm@example.com",),
            "scheduling_lead": ("sched@example.com",),
        },
        environ={},
    )
    assert to == ("cm@example.com",)
    assert cc == ("sched@example.com",)


def test_resolve_dedupes_cc_already_in_to() -> None:
    to, cc = resolve_recipients(
        ("management",),
        ("assigned_cm",),
        case_emails={
            "management": ("same@example.com",),
            "assigned_cm": ("same@example.com",),
        },
        environ={},
    )
    assert to == ("same@example.com",)
    assert cc == ()


def test_missing_case_email_fails_closed() -> None:
    with pytest.raises(GmailAlertConfigError, match="No email on this case"):
        resolve_recipients(("intake_lead",), case_emails={}, environ={})


def test_default_to_overrides_case_emails() -> None:
    to, cc = resolve_recipients(
        ("assigned_cm",),
        ("scheduling_lead",),
        case_emails={"assigned_cm": ("cm@example.com",)},
        environ={"GMAIL_ALERT_DEFAULT_TO": "demo@example.com"},
    )
    assert to == ("demo@example.com",)
    assert cc == ()
