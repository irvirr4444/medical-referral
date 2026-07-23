"""Refresh schemas and derived metadata for an existing local Monday export."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from export_monday_boards import SCHEMA_QUERY
from monday_api import DEFAULT_API_VERSION, DEFAULT_TIMEOUT_S, monday_graphql
from monday_board_metadata import build_board_metadata


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _board_directory(export_dir: Path, board: dict[str, Any]) -> Path:
    return export_dir / str(board.get("directory") or f"boards/{board['id']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Refresh schema and metadata for an existing Monday export.")
    parser.add_argument("export_dir", type=Path)
    parser.add_argument("--api-version", default=DEFAULT_API_VERSION)
    parser.add_argument("--timeout-s", type=int, default=DEFAULT_TIMEOUT_S)
    args = parser.parse_args(argv)

    manifest = _read_json(args.export_dir / "manifest.json")
    board_ids = [str(board["id"]) for board in manifest["boards"] if board.get("status") == "exported"]
    response = monday_graphql(
        SCHEMA_QUERY,
        variables={"boardIds": board_ids},
        api_version=args.api_version,
        timeout_s=args.timeout_s,
    )
    schemas = {str(board["id"]): board for board in response.get("data", {}).get("boards") or []}

    for board_id in board_ids:
        board = next(board for board in manifest["boards"] if str(board["id"]) == board_id)
        board_dir = _board_directory(args.export_dir, board)
        schema = schemas.get(board_id)
        if schema is None:
            print(f"[{board_id}] schema unavailable; existing records retained")
            continue
        items = _read_json(board_dir / "records.json")["items"]
        _write_json(board_dir / "schema.json", schema)
        _write_json(board_dir / "metadata.json", build_board_metadata(schema, items))
        print(f"[{board_id}] refreshed schema and metadata")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
