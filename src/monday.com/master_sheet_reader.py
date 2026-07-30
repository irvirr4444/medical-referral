"""Read-only helpers for the WCW Monday.com Master Sheet.

The Master Sheet contains PHI. These helpers intentionally return only selected
fields to CLI callers and never write to Monday.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Any

from monday_api import DEFAULT_API_VERSION, DEFAULT_TIMEOUT_S, monday_graphql


MASTER_SHEET_BOARD_ID = "5815942462"

# Aliases keep callers independent of Monday's opaque column IDs.
FIELD_COLUMNS: dict[str, str] = {
    "name": "name",
    "dob": "date12",
    "patient_phone": "phone",
    "patient_address": "location",
    "referral_received": "date7",
    "pos": "status_1__1",
    "agency_contact": "text6__1",
    "agency_phone": "text41__1",
    "stage": "deal_stage",
    "case_manager": "deal_owner",
    "sent_to_cm": "status7__1",
    "referral_sent_to_provider": "status3__1",
    "appointment_date": "date9__1",
    "scheduling_complete": "status0__1",
    "scheduled_status": "color_mkq3gga",
    "visit_status": "status5__1",
    "qa_hold_reason": "label99",
    "discharge_reason": "color_mm1mssvv",
}

DEFAULT_RESULT_FIELDS = (
    "name",
    "dob",
    "referral_received",
    "case_manager",
    "sent_to_cm",
    "scheduled_status",
    "scheduling_complete",
    "visit_status",
)

# These aliases map to column types supported by Monday's
# `items_page_by_column_values` query. Full summaries can still inspect every
# alias, but targeted operational reports should stay on the server-side path.
SERVER_FILTERABLE_FIELDS = frozenset(
    {
        "name",
        "dob",
        "patient_phone",
        "referral_received",
        "pos",
        "stage",
        "case_manager",
        "sent_to_cm",
        "referral_sent_to_provider",
        "appointment_date",
        "scheduling_complete",
        "scheduled_status",
        "visit_status",
        "qa_hold_reason",
        "discharge_reason",
    }
)

FIRST_PAGE_QUERY = """
query ($boardIds: [ID!], $limit: Int!) {
  boards(ids: $boardIds) {
    id
    name
    columns { id title type }
    items_page(limit: $limit) {
      cursor
      items {
        id
        name
        group { id title }
        column_values { id text }
      }
    }
  }
}
"""

NEXT_PAGE_QUERY = """
query ($cursor: String!, $limit: Int!) {
  next_items_page(cursor: $cursor, limit: $limit) {
    cursor
    items {
      id
      name
      group { id title }
      column_values { id text }
    }
  }
}
"""

FILTERED_FIRST_PAGE_QUERY = """
query ($boardId: ID!, $columns: [ItemsPageByColumnValuesQuery!]!, $limit: Int!) {
  items_page_by_column_values(board_id: $boardId, columns: $columns, limit: $limit) {
    cursor
    items {
      id
      name
      group { id title }
      column_values { id text }
    }
  }
}
"""

NAME_SEARCH_FIRST_PAGE_QUERY = """
query ($boardIds: [ID!], $term: CompareValue!, $limit: Int!) {
  boards(ids: $boardIds) {
    items_page(
      limit: $limit,
      query_params: {
        rules: [{column_id: "name", compare_value: $term, operator: contains_text}]
      }
    ) {
      cursor
      items {
        id
        name
        group { id title }
        column_values { id text }
      }
    }
  }
}
"""

QueryFn = Callable[..., dict[str, Any]]


@dataclass(frozen=True)
class FilteredItems:
    """Server-filtered rows and whether a capped query has more results."""

    items: list[dict[str, Any]]
    has_more: bool


def normalize_name(value: str | None) -> str:
    """Normalize punctuation and whitespace for a cautious name comparison."""
    text = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
    return " ".join(re.sub(r"[^A-Za-z0-9]+", " ", text).upper().split())


def _name_match_key(value: str | None) -> tuple[str, ...]:
    """Make `Last, First` and `First Last` comparable without fuzzy matching."""
    return tuple(sorted(normalize_name(value).split()))


def normalize_dob(value: str | None) -> str:
    """Normalize common Monday/PDF DOB formats to digits for matching."""
    text = (value or "").strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%m%d%Y")
        except ValueError:
            continue
    return "".join(ch for ch in text if ch.isdigit())


def item_values(item: dict[str, Any]) -> dict[str, str]:
    """Return a row's displayed values keyed by stable integration aliases."""
    by_column = {str(value.get("id")): str(value.get("text") or "") for value in item.get("column_values") or []}
    values = {alias: by_column.get(column_id, "") for alias, column_id in FIELD_COLUMNS.items()}
    values["name"] = str(item.get("name") or "")
    return values


def load_export_items(records_path: str | Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Load one board's locally exported records without contacting Monday."""
    path = Path(records_path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except OSError as error:
        raise RuntimeError(f"Could not read export records file: {path}") from error
    except json.JSONDecodeError as error:
        raise RuntimeError(f"Export records file is not valid JSON: {path}") from error
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        raise RuntimeError(f"Export records file does not contain an items list: {path}")
    board = payload.get("board") if isinstance(payload.get("board"), dict) else {}
    return board, items


def select_fields(item: dict[str, Any], fields: tuple[str, ...] = DEFAULT_RESULT_FIELDS) -> dict[str, Any]:
    """Build a compact, PHI-minimizing row representation for CLI output."""
    values = item_values(item)
    return {
        "id": str(item.get("id") or ""),
        "group": str((item.get("group") or {}).get("title") or ""),
        "fields": {field: values.get(field, "") for field in fields},
    }


def fetch_items(
    *,
    board_id: str = MASTER_SHEET_BOARD_ID,
    page_size: int = 500,
    query_fn: QueryFn = monday_graphql,
    api_version: str = DEFAULT_API_VERSION,
    timeout_s: int = DEFAULT_TIMEOUT_S,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Fetch every top-level item from a board using Monday cursor pagination."""
    if not 1 <= page_size <= 500:
        raise ValueError("page_size must be between 1 and 500")

    response = query_fn(
        FIRST_PAGE_QUERY,
        variables={"boardIds": [str(board_id)], "limit": page_size},
        api_version=api_version,
        timeout_s=timeout_s,
    )
    boards = response.get("data", {}).get("boards") or []
    if not boards:
        raise RuntimeError(f"Board {board_id} was not returned by Monday.")

    board = boards[0]
    page = board.get("items_page") or {}
    items = list(page.get("items") or [])
    cursor = page.get("cursor")
    while cursor:
        response = query_fn(
            NEXT_PAGE_QUERY,
            variables={"cursor": cursor, "limit": page_size},
            api_version=api_version,
            timeout_s=timeout_s,
        )
        page = response.get("data", {}).get("next_items_page") or {}
        page_items = page.get("items") or []
        if not page_items:
            break
        items.extend(page_items)
        cursor = page.get("cursor")

    return {key: value for key, value in board.items() if key != "items_page"}, items


def fetch_items_by_column_value(
    *,
    field: str,
    value: str,
    board_id: str = MASTER_SHEET_BOARD_ID,
    page_size: int = 500,
    max_items: int | None = None,
    query_fn: QueryFn = monday_graphql,
    api_version: str = DEFAULT_API_VERSION,
    timeout_s: int = DEFAULT_TIMEOUT_S,
) -> FilteredItems:
    """Fetch matching rows through Monday's server-side column filter."""
    if field not in SERVER_FILTERABLE_FIELDS:
        raise ValueError(f"{field!r} is not supported by the server-side filter")
    if not value:
        raise ValueError("A server-side filter value cannot be blank")
    if not 1 <= page_size <= 500:
        raise ValueError("page_size must be between 1 and 500")
    if max_items is not None and max_items < 1:
        raise ValueError("max_items must be at least 1 when provided")

    first_limit = min(page_size, max_items) if max_items is not None else page_size

    response = query_fn(
        FILTERED_FIRST_PAGE_QUERY,
        variables={
            "boardId": str(board_id),
            "limit": first_limit,
            "columns": [{"column_id": FIELD_COLUMNS[field], "column_values": [value]}],
        },
        api_version=api_version,
        timeout_s=timeout_s,
    )
    page = response.get("data", {}).get("items_page_by_column_values") or {}
    items = list(page.get("items") or [])
    cursor = page.get("cursor")
    while cursor and (max_items is None or len(items) < max_items):
        next_limit = min(page_size, max_items - len(items)) if max_items is not None else page_size
        response = query_fn(
            NEXT_PAGE_QUERY,
            variables={"cursor": cursor, "limit": next_limit},
            api_version=api_version,
            timeout_s=timeout_s,
        )
        page = response.get("data", {}).get("next_items_page") or {}
        page_items = page.get("items") or []
        if not page_items:
            break
        items.extend(page_items)
        cursor = page.get("cursor")
    return FilteredItems(items=items, has_more=bool(cursor))


def fetch_items_by_name_search(
    *,
    name: str,
    board_id: str = MASTER_SHEET_BOARD_ID,
    page_size: int = 500,
    max_items: int | None = None,
    query_fn: QueryFn = monday_graphql,
    api_version: str = DEFAULT_API_VERSION,
    timeout_s: int = DEFAULT_TIMEOUT_S,
) -> FilteredItems:
    """Fetch a narrow name candidate set using Monday's partial-name filter."""
    if not 1 <= page_size <= 500:
        raise ValueError("page_size must be between 1 and 500")
    if max_items is not None and max_items < 1:
        raise ValueError("max_items must be at least 1 when provided")
    tokens = normalize_name(name).split()
    if not tokens:
        raise ValueError("name must contain at least one letter or number")

    # A discriminating token supports `Last, First` and `First Last` without
    # retrieving the full board. Local matching remains stricter.
    search_term = max(tokens, key=len)
    first_limit = min(page_size, max_items) if max_items is not None else page_size
    response = query_fn(
        NAME_SEARCH_FIRST_PAGE_QUERY,
        variables={"boardIds": [str(board_id)], "term": [search_term], "limit": first_limit},
        api_version=api_version,
        timeout_s=timeout_s,
    )
    boards = response.get("data", {}).get("boards") or []
    if not boards:
        raise RuntimeError(f"Board {board_id} was not returned by Monday.")
    page = boards[0].get("items_page") or {}
    items = list(page.get("items") or [])
    cursor = page.get("cursor")
    while cursor and (max_items is None or len(items) < max_items):
        next_limit = min(page_size, max_items - len(items)) if max_items is not None else page_size
        response = query_fn(
            NEXT_PAGE_QUERY,
            variables={"cursor": cursor, "limit": next_limit},
            api_version=api_version,
            timeout_s=timeout_s,
        )
        page = response.get("data", {}).get("next_items_page") or {}
        page_items = page.get("items") or []
        if not page_items:
            break
        items.extend(page_items)
        cursor = page.get("cursor")
    return FilteredItems(items=items, has_more=bool(cursor))


def find_patients(
    items: list[dict[str, Any]],
    *,
    name: str,
    dob: str | None = None,
    contains: bool = False,
) -> list[dict[str, Any]]:
    """Find exact normalized-name candidates, optionally narrowed by DOB.

    The result is deliberately a candidate list. A matching name and DOB does
    not prove two referrals are the same patient.
    """
    target_name = normalize_name(name)
    target_name_key = _name_match_key(name)
    target_dob = normalize_dob(dob)
    if not target_name:
        raise ValueError("name must contain at least one letter or number")

    matches: list[dict[str, Any]] = []
    for item in items:
        values = item_values(item)
        candidate_name = normalize_name(values["name"])
        name_matches = target_name in candidate_name if contains else target_name_key == _name_match_key(values["name"])
        if not name_matches:
            continue
        if target_dob and normalize_dob(values["dob"]) != target_dob:
            continue
        matches.append(item)
    return matches


def filter_by_field(
    items: list[dict[str, Any]],
    *,
    field: str,
    equals: str | None = None,
    not_equals: str | None = None,
) -> list[dict[str, Any]]:
    """Filter rows by an exact displayed field value without making workflow assumptions."""
    if field not in FIELD_COLUMNS:
        raise ValueError(f"Unknown field {field!r}. Choose one of: {', '.join(sorted(FIELD_COLUMNS))}")
    if (equals is None) == (not_equals is None):
        raise ValueError("Provide exactly one of equals or not_equals")

    expected = equals if equals is not None else not_equals
    assert expected is not None
    selected: list[dict[str, Any]] = []
    for item in items:
        value = item_values(item).get(field, "")
        if (equals is not None and value == expected) or (not_equals is not None and value != expected):
            selected.append(item)
    return selected


def count_field_values(items: list[dict[str, Any]], *, field: str) -> list[dict[str, Any]]:
    """Return populated and blank value counts for a named field."""
    if field not in FIELD_COLUMNS:
        raise ValueError(f"Unknown field {field!r}. Choose one of: {', '.join(sorted(FIELD_COLUMNS))}")
    counts: dict[str, int] = {}
    for item in items:
        value = item_values(item).get(field, "") or "<blank>"
        counts[value] = counts.get(value, 0) + 1
    return [{"value": value, "count": count} for value, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))]
