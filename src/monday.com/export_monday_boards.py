"""Read-only Monday board exporter for local CRM discovery.

Exports raw rows separately from derived metadata. The raw export can contain PHI,
so use a local ignored directory and never point this at a repository path meant for commits.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from monday_api import DEFAULT_API_VERSION, DEFAULT_TIMEOUT_S, MondayAPIError, monday_graphql
from monday_board_metadata import build_board_metadata, relation_targets


SCHEMA_QUERY = """
query ($boardIds: [ID!]) {
  boards(ids: $boardIds) {
    id name description board_kind state
    groups { id title }
    columns { id title type settings_str }
  }
}
"""

FIRST_PAGE_QUERY = """
query ($boardIds: [ID!], $limit: Int!) {
  boards(ids: $boardIds) {
    id name description board_kind state
    groups { id title }
    columns { id title type settings_str }
    items_page(limit: $limit) {
      cursor
      items {
        id name created_at updated_at
        group { id title }
        column_values { __COLUMN_VALUE_FIELDS__ }
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
      id name created_at updated_at
      group { id title }
      column_values { __COLUMN_VALUE_FIELDS__ }
    }
  }
}
"""


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _board_directory_name(board: dict[str, Any], used_names: set[str]) -> str:
    """Make local export paths understandable while keeping them unique."""
    normalized = unicodedata.normalize("NFKD", str(board.get("name") or "board"))
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii").lower()
    base = re.sub(r"[^a-z0-9]+", "-", ascii_name).strip("-") or "board"
    name = base
    if name in used_names:
        name = f"{base}-{board['id']}"
    used_names.add(name)
    return name


def _page_query(query: str, *, include_raw_values: bool) -> str:
    fields = "id text type value" if include_raw_values else "id text type"
    return query.replace("__COLUMN_VALUE_FIELDS__", fields)


def _is_retryable_graphql_error(error: MondayAPIError) -> bool:
    """Monday reports complexity/rate limits as GraphQL errors with HTTP 200."""
    response = json.dumps(error.response or {}).lower()
    retry_markers = (
        "complexity",
        "rate limit",
        "rate_limit",
        "quota",
        "too many requests",
        "limit exceeded",
        "exceeded the limit",
    )
    return any(marker in response for marker in retry_markers)


def _query_with_backoff(
    query: str,
    *,
    variables: dict[str, Any],
    api_version: str,
    timeout_s: int,
    max_rate_limit_retries: int,
    rate_limit_wait_s: int,
) -> dict[str, Any]:
    for attempt in range(max_rate_limit_retries + 1):
        try:
            return monday_graphql(
                query,
                variables=variables,
                api_version=api_version,
                timeout_s=timeout_s,
            )
        except MondayAPIError as error:
            if attempt == max_rate_limit_retries:
                error_kind = "capacity" if _is_retryable_graphql_error(error) else "unexpected"
                raise MondayAPIError(
                    f"Monday {error_kind} GraphQL error persisted after retries.",
                    status=error.status,
                    response=error.response,
                ) from error
            error_kind = "capacity limit" if _is_retryable_graphql_error(error) else "temporary GraphQL error"
            print(
                f"Monday {error_kind}; waiting {rate_limit_wait_s}s before retry "
                f"({attempt + 1}/{max_rate_limit_retries})",
                file=sys.stderr,
                flush=True,
            )
            time.sleep(rate_limit_wait_s)
    raise AssertionError("unreachable")


def _read_board(board_id: str, *, api_version: str, timeout_s: int) -> dict[str, Any] | None:
    response = _query_with_backoff(
        SCHEMA_QUERY,
        variables={"boardIds": [board_id]},
        api_version=api_version,
        timeout_s=timeout_s,
        max_rate_limit_retries=3,
        rate_limit_wait_s=60,
    )
    boards = response.get("data", {}).get("boards") or []
    return boards[0] if boards else None


def _fetch_items(
    board_id: str,
    *,
    page_size: int,
    api_version: str,
    timeout_s: int,
    max_rate_limit_retries: int,
    rate_limit_wait_s: int,
    include_raw_values: bool,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    response = _query_with_backoff(
        _page_query(FIRST_PAGE_QUERY, include_raw_values=include_raw_values),
        variables={"boardIds": [board_id], "limit": page_size},
        api_version=api_version,
        timeout_s=timeout_s,
        max_rate_limit_retries=max_rate_limit_retries,
        rate_limit_wait_s=rate_limit_wait_s,
    )
    boards = response.get("data", {}).get("boards") or []
    if not boards:
        return None, []

    board = boards[0]
    page = board.pop("items_page")
    items = list(page.get("items") or [])
    cursor = page.get("cursor")
    page_number = 1
    print(f"[{board_id}] page {page_number}: {len(items)} records", file=sys.stderr, flush=True)

    while cursor:
        response = _query_with_backoff(
            _page_query(NEXT_PAGE_QUERY, include_raw_values=include_raw_values),
            variables={"cursor": cursor, "limit": page_size},
            api_version=api_version,
            timeout_s=timeout_s,
            max_rate_limit_retries=max_rate_limit_retries,
            rate_limit_wait_s=rate_limit_wait_s,
        )
        page = response.get("data", {}).get("next_items_page") or {}
        page_items = page.get("items") or []
        if not page_items:
            break
        items.extend(page_items)
        cursor = page.get("cursor")
        page_number += 1
        print(f"[{board_id}] page {page_number}: {len(items)} records total", file=sys.stderr, flush=True)

    return board, items


def _export_board(
    board_id: str,
    *,
    output_dir: Path,
    page_size: int,
    api_version: str,
    timeout_s: int,
    max_rate_limit_retries: int,
    rate_limit_wait_s: int,
    include_raw_values: bool,
    used_directory_names: set[str],
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    board, items = _fetch_items(
        board_id,
        page_size=page_size,
        api_version=api_version,
        timeout_s=timeout_s,
        max_rate_limit_retries=max_rate_limit_retries,
        rate_limit_wait_s=rate_limit_wait_s,
        include_raw_values=include_raw_values,
    )
    if board is None:
        return None, {"id": board_id, "status": "unavailable"}

    directory_name = _board_directory_name(board, used_directory_names)
    board_dir = output_dir / "boards" / directory_name
    _write_json(board_dir / "schema.json", board)
    _write_json(board_dir / "records.json", {"board": {"id": board_id, "name": board.get("name")}, "items": items})
    _write_json(board_dir / "metadata.json", build_board_metadata(board, items))
    return board, {
        "id": board_id,
        "name": board.get("name"),
        "directory": f"boards/{directory_name}",
        "record_count": len(items),
        "status": "exported",
    }


def _direct_related_board_ids(board: dict[str, Any]) -> Iterable[str]:
    seen: set[str] = set()
    for board_ids in relation_targets(board).values():
        for board_id in board_ids:
            if board_id not in seen:
                seen.add(board_id)
                yield board_id


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export Monday boards and local integration metadata.")
    parser.add_argument("--board-id", default="5815942462", help="Root board ID (default: Master Sheet).")
    parser.add_argument("--output-dir", type=Path, help="Local output directory. Defaults to a timestamped tmp export.")
    parser.add_argument("--include-related", action="store_true", help="Also export every board directly linked by the root board.")
    parser.add_argument("--page-size", type=int, default=500, choices=range(1, 501), metavar="1..500")
    parser.add_argument("--api-version", default=DEFAULT_API_VERSION)
    parser.add_argument("--timeout-s", type=int, default=DEFAULT_TIMEOUT_S)
    parser.add_argument("--max-rate-limit-retries", type=int, default=6)
    parser.add_argument("--rate-limit-wait-s", type=int, default=60)
    parser.add_argument(
        "--include-raw-values",
        action="store_true",
        help="Also save Monday's internal column JSON. This substantially increases export size and API load.",
    )
    args = parser.parse_args(argv)

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output_dir = args.output_dir or Path("tmp") / "monday-exports" / timestamp
    output_dir.mkdir(parents=True, exist_ok=False)
    used_directory_names: set[str] = set()

    root_board, root_summary = _export_board(
        str(args.board_id),
        output_dir=output_dir,
        page_size=args.page_size,
        api_version=args.api_version,
        timeout_s=args.timeout_s,
        max_rate_limit_retries=args.max_rate_limit_retries,
        rate_limit_wait_s=args.rate_limit_wait_s,
        include_raw_values=args.include_raw_values,
        used_directory_names=used_directory_names,
    )
    summaries = [root_summary]
    if root_board and args.include_related:
        for related_id in _direct_related_board_ids(root_board):
            if related_id == str(args.board_id):
                continue
            related_board, summary = _export_board(
                related_id,
                output_dir=output_dir,
                page_size=args.page_size,
                api_version=args.api_version,
                timeout_s=args.timeout_s,
                max_rate_limit_retries=args.max_rate_limit_retries,
                rate_limit_wait_s=args.rate_limit_wait_s,
                include_raw_values=args.include_raw_values,
                used_directory_names=used_directory_names,
            )
            summaries.append(summary)
            if related_board is None:
                print(f"[{related_id}] unavailable to this token; continuing", file=sys.stderr)

    _write_json(
        output_dir / "manifest.json",
        {
            "generated_at": datetime.now(UTC).isoformat(),
            "root_board_id": str(args.board_id),
            "include_related": args.include_related,
            "include_raw_values": args.include_raw_values,
            "boards": summaries,
        },
    )
    print(f"Export complete: {output_dir}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
