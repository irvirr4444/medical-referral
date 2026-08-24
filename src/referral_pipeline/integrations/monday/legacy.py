"""Compatibility boundary for the legacy ``src/monday.com`` scripts.

The old directory is still used by the intake code and is not an importable
Python package. New production integration code should depend on this small
adapter instead of modifying ``sys.path`` in business logic modules.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

SRC_ROOT = Path(__file__).resolve().parents[3]
LEGACY_MONDAY_DIR = SRC_ROOT / "monday.com"
if str(LEGACY_MONDAY_DIR) not in sys.path:
    sys.path.insert(0, str(LEGACY_MONDAY_DIR))

from master_sheet_reader import FIELD_COLUMNS, fetch_items_by_ids  # noqa: E402
from monday_api import monday_graphql  # noqa: E402


def fetch_items_by_ids_readonly(*, ids: list[str]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Fetch Monday items through the existing read-only reader."""

    return fetch_items_by_ids(ids=ids)


__all__ = ["FIELD_COLUMNS", "fetch_items_by_ids_readonly", "monday_graphql"]
