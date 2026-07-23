"""Pure helpers for turning Monday board exports into integration metadata."""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from typing import Any


READ_ONLY_COLUMN_TYPES = {"formula", "mirror", "subtasks"}


def parse_settings(settings_str: str | None) -> dict[str, Any]:
    """Return Monday column settings without failing on malformed legacy settings."""
    if not settings_str:
        return {}
    try:
        value = json.loads(settings_str)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def related_board_ids(column: dict[str, Any]) -> list[str]:
    settings = parse_settings(column.get("settings_str"))
    board_ids = settings.get("boardIds")
    if not isinstance(board_ids, list):
        return []
    return [str(board_id) for board_id in board_ids]


def column_relationship(column: dict[str, Any]) -> dict[str, Any]:
    """Describe how a column relates to other Monday structures."""
    column_type = str(column.get("type") or "")
    settings = parse_settings(column.get("settings_str"))
    if column_type == "board_relation":
        return {"kind": "board_relation", "target_board_ids": related_board_ids(column)}
    if column_type == "mirror":
        linked_columns = settings.get("displayed_linked_columns")
        linked_columns = linked_columns if isinstance(linked_columns, dict) else {}
        return {
            "kind": "mirror",
            "source_relation_column_ids": sorted((settings.get("relation_column") or {}).keys()),
            "target_board_ids": sorted(str(board_id) for board_id in linked_columns),
            "target_column_ids": {
                str(board_id): values
                for board_id, values in linked_columns.items()
                if isinstance(values, list)
            },
        }
    if column_type == "subtasks":
        return {"kind": "subitems", "target_board_ids": related_board_ids(column)}
    if column_type == "formula":
        return {"kind": "derived_formula"}
    return {"kind": "direct_on_this_board"}


def population_measurement(column: dict[str, Any]) -> str:
    """Explain what a populated percentage does and does not prove."""
    if column.get("type") in {"board_relation", "mirror", "subtasks"}:
        return "display_text_only; an empty value does not prove the underlying link is empty"
    return "display_text"


def allowed_values(column: dict[str, Any]) -> list[str]:
    """Extract configured status/dropdown labels in their display order when available."""
    settings = parse_settings(column.get("settings_str"))
    labels = settings.get("labels")
    if isinstance(labels, dict):
        positions = settings.get("labels_positions_v2")
        items = labels.items()
        if isinstance(positions, dict):
            items = sorted(items, key=lambda item: positions.get(str(item[0]), 10_000))
        return [str(label) for _, label in items if label]
    if isinstance(labels, list):
        return [str(label["name"]) for label in labels if isinstance(label, dict) and label.get("name")]
    return []


def automation_classification(column: dict[str, Any]) -> str:
    column_type = column.get("type")
    if column_type in READ_ONLY_COLUMN_TYPES:
        return "derived_read_only"
    if column_type == "board_relation":
        return "relation_requires_lookup"
    if column_type in {"name", "text", "email", "phone", "location", "date", "status", "dropdown"}:
        return "direct_write_candidate"
    return "manual_or_workflow_field"


def build_board_metadata(board: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, Any]:
    """Build JSON-safe schema, relation, and population metadata for one board."""
    populated = Counter()
    groups = Counter()
    for item in items:
        group = item.get("group") or {}
        groups[str(group.get("title") or "Ungrouped")] += 1
        for value in item.get("column_values") or []:
            if value.get("text") not in (None, "") or value.get("value") not in (None, ""):
                populated[str(value.get("id"))] += 1

    columns: list[dict[str, Any]] = []
    for column in board.get("columns") or []:
        column_id = str(column["id"])
        populated_count = (
            sum(bool(item.get("name")) for item in items)
            if column.get("type") == "name"
            else populated[column_id]
        )
        columns.append(
            {
                "id": column_id,
                "title": column.get("title"),
                "type": column.get("type"),
                "automation_classification": automation_classification(column),
                "configured_values": allowed_values(column),
                "related_board_ids": related_board_ids(column),
                "relationship": column_relationship(column),
                "population_measurement": population_measurement(column),
                "populated_item_count": populated_count,
                "populated_percent": round((populated_count / len(items)) * 100, 2) if items else 0,
            }
        )

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "board": {
            "id": str(board["id"]),
            "name": board.get("name"),
            "description": board.get("description"),
            "kind": board.get("board_kind"),
            "state": board.get("state"),
        },
        "record_count": len(items),
        "groups": [{"title": title, "item_count": count} for title, count in groups.most_common()],
        "columns": columns,
    }


def relation_targets(board: dict[str, Any]) -> dict[str, list[str]]:
    """Map each relation column ID to the direct board IDs it references."""
    return {
        str(column["id"]): related_board_ids(column)
        for column in board.get("columns") or []
        if column.get("type") == "board_relation" and related_board_ids(column)
    }
