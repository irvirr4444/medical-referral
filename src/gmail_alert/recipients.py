"""Resolve To/Cc from the case — not from fixed role env vars.

Each run has a different CM, provider, etc. Pass those addresses on the
alert context. ``GMAIL_ALERT_DEFAULT_TO`` is a demo-only sink that overrides
everything when set.
"""

from __future__ import annotations

import os

from gmail_alert.ids import RecipientRole

DEFAULT_TO_ENV = "GMAIL_ALERT_DEFAULT_TO"


class GmailAlertConfigError(RuntimeError):
    """Missing or empty Gmail alert configuration."""


def parse_address_list(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return ()
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def resolve_recipients(
    to_roles: tuple[RecipientRole, ...],
    cc_roles: tuple[RecipientRole, ...] = (),
    *,
    case_emails: dict[RecipientRole, tuple[str, ...]] | None = None,
    environ: dict[str, str] | None = None,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Map template roles to addresses from the case. Fail closed if a To role is empty.

    If GMAIL_ALERT_DEFAULT_TO is set (demo), every alert goes only there.
    """

    env = os.environ if environ is None else environ
    default = parse_address_list(env.get(DEFAULT_TO_ENV, ""))
    if default:
        return default, ()

    by_role = case_emails or {}
    to: list[str] = []
    seen: set[str] = set()
    for role in to_roles:
        addresses = tuple(addr for addr in by_role.get(role, ()) if addr)
        if not addresses:
            raise GmailAlertConfigError(
                f"No email on this case for role {role!r} — pass case-specific addresses"
            )
        for address in addresses:
            if address not in seen:
                seen.add(address)
                to.append(address)

    cc: list[str] = []
    for role in cc_roles:
        addresses = tuple(addr for addr in by_role.get(role, ()) if addr)
        if not addresses:
            raise GmailAlertConfigError(
                f"No email on this case for role {role!r} — pass case-specific addresses"
            )
        for address in addresses:
            if address not in seen:
                seen.add(address)
                cc.append(address)
    return tuple(to), tuple(cc)
