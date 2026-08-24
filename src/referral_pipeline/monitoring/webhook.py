"""Compatibility facade for the Monday webhook integration.

New code lives under ``referral_pipeline.integrations.monday``. This module
keeps the original imports stable while the legacy Monday scripts are moved
behind a single adapter boundary.
"""

from referral_pipeline.integrations.monday.webhook_auth import (
    WebhookAuthError,
    verify_webhook_token,
)
from referral_pipeline.integrations.monday.webhook_contract import (
    STAGE_WEBHOOK_COLUMN_ALIASES,
    WEBHOOK_COLUMN_ALIASES,
    WEBHOOK_COLUMN_IDS,
)
from referral_pipeline.integrations.monday.webhook_processor import process_webhook_payload

handle_webhook_payload = process_webhook_payload

__all__ = [
    "STAGE_WEBHOOK_COLUMN_ALIASES",
    "WEBHOOK_COLUMN_ALIASES",
    "WEBHOOK_COLUMN_IDS",
    "WebhookAuthError",
    "handle_webhook_payload",
    "verify_webhook_token",
]
