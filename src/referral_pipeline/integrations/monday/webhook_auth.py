"""Authentication helpers for Monday webhook deliveries."""

from __future__ import annotations

import hmac


class WebhookAuthError(Exception):
    """Raised when a webhook request fails the shared-secret check."""


def verify_webhook_token(
    query_token: str | None,
    *,
    expected: str | None,
    header_token: str | None = None,
) -> None:
    """Accept the header form first, retaining query-token compatibility."""

    if not expected:
        raise WebhookAuthError("MONDAY_WEBHOOK_TOKEN is not configured")
    supplied = header_token or query_token
    if not supplied or not hmac.compare_digest(str(supplied), str(expected)):
        raise WebhookAuthError("invalid or missing webhook token")
