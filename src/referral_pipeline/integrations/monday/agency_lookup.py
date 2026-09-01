"""Exact, read-only agency matching for the Master Sheet relation column."""

from __future__ import annotations

from pathlib import Path

from referral_pipeline.integrations.monday.reader import (
    fetch_items_by_name_search,
    load_export_items,
    normalize_name,
)


def find_agency_matches_from_snapshot(name: str | None, *, records_file: str | Path) -> list[dict[str, str]]:
    """Find exact normalized account names in a local Accounts board export."""
    _, items = load_export_items(records_file)
    return _exact_name_matches(name, items)


def find_agency_matches_live(name: str | None, *, board_id: str) -> list[dict[str, str]]:
    """Find exact normalized account names through Monday's read-only API."""
    if not normalize_name(name):
        return []
    result = fetch_items_by_name_search(name=name or "", board_id=board_id, max_items=None)
    return _exact_name_matches(name, result.items)


def _exact_name_matches(name: str | None, items: list[dict]) -> list[dict[str, str]]:
    target = normalize_name(name)
    if not target:
        return []
    return [
        {"id": str(item.get("id") or ""), "name": str(item.get("name") or "")}
        for item in items
        if normalize_name(str(item.get("name") or "")) == target
    ]
