"""Generate PHI-free Master Sheet reference guides from a local Monday export."""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any


MASTER_SHEET_ID = "5815942462"


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _escape(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return ascii_value.replace("|", "\\|").replace("\n", " ")


def _settings(column: dict[str, Any]) -> dict[str, Any]:
    raw = column.get("settings_str") or "{}"
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _category(column: dict[str, Any]) -> str:
    column_type = column.get("type")
    if column_type in {"mirror", "formula", "subtasks"}:
        return "Derived and linked data"
    if column_type == "board_relation":
        return "Board relationships"
    title = str(column.get("title") or "").lower()
    if any(word in title for word in ("patient", "pt ", "referral received", "pos", "name")):
        return "Patient and referral intake"
    if any(word in title for word in ("agency", "marketer", "rep", "account", "company", "contact", "territory", "legal")):
        return "Agency and source relationship"
    if any(word in title for word in ("case manager", "sent", "intake", "nexus", "owner")):
        return "Intake handoff and assignment"
    if any(word in title for word in ("provider", "appoint", "schedul", "route", "outsource")):
        return "Provider and scheduling"
    if any(word in title for word in ("hold", "visit", "progress", "follow", "discharge", "dc ", "deceased")):
        return "Visit, hold, and discharge"
    if any(word in title for word in ("deal", "forecast", "priority", "actual", "activities", "expected close")):
        return "CRM and sales tracking"
    return "Other operational fields"


def _field_purpose(column: dict[str, Any]) -> str:
    title = str(column.get("title") or "Untitled")
    column_type = str(column.get("type") or "unknown")
    special = {
        "name": "Primary label for the Master Sheet item; this is the row's visible identity.",
        "deal_stage": "Current intake marker in the observed data. It is not reliable as the historical lifecycle state.",
        "status5__1": "Primary observed operational lifecycle signal in the snapshot, including seen, hold, scheduled, and discharge-related values.",
        "date7": "Date/time WCW recorded the referral as received.",
        "date12": "Patient date of birth.",
        "status_1__1": "Point of service/location category used by WCW.",
        "text00__1": "Free-text operational comments.",
        "dropdown_mm1t7rd3": "Configured discharge reason selection; useful only after an appropriate discharge decision.",
    }
    if column.get("id") in special:
        return special[str(column["id"])]
    type_purposes = {
        "text": f"Free-text value for '{title}'.",
        "date": f"Date or date/time value for '{title}'.",
        "status": f"Controlled workflow/status value for '{title}'.",
        "dropdown": f"Controlled selection list for '{title}'.",
        "email": f"Email value for '{title}'.",
        "phone": f"Phone value for '{title}'.",
        "location": f"Location/address value for '{title}'.",
        "people": f"Monday user/person assignment for '{title}'.",
        "numbers": f"Numeric value for '{title}'.",
        "hour": f"Time-of-day value for '{title}'.",
        "time_tracking": f"Time-tracking value for '{title}'.",
    }
    return type_purposes.get(column_type, f"{column_type.replace('_', ' ').capitalize()} field for '{title}'.")


def _formula_relationship(column: dict[str, Any], master_columns: dict[str, dict[str, Any]]) -> str:
    formula = str(_settings(column).get("formula") or "")
    references = re.findall(r"\{([^}]+)\}", formula)
    titles: list[str] = []
    for reference in references:
        column_id = reference.split("#", maxsplit=1)[0]
        title = master_columns.get(column_id, {}).get("title")
        if title and title not in titles:
            titles.append(str(title))
    if not titles:
        return "Calculated from other Master Sheet fields; see the raw schema formula if the exact expression matters."
    suffix = "" if len(titles) <= 6 else " and additional fields"
    return "Calculated from: " + ", ".join(titles[:6]) + suffix + "."


def _relationship_summary(
    column: dict[str, Any],
    master_columns: dict[str, dict[str, Any]],
    schemas: dict[str, dict[str, Any]],
) -> str:
    column_type = column.get("type")
    settings = _settings(column)
    if column_type == "board_relation":
        target_ids = settings.get("boardIds") or []
        targets = [str(schemas.get(str(board_id), {}).get("name") or f"board {board_id}") for board_id in target_ids]
        return "Links this item to " + (", ".join(targets) if targets else "another Monday board") + "."
    if column_type == "mirror":
        relation_ids = sorted((settings.get("relation_column") or {}).keys())
        relation_names = [str(master_columns.get(column_id, {}).get("title") or column_id) for column_id in relation_ids]
        linked = settings.get("displayed_linked_columns") or {}
        targets: list[str] = []
        for board_id, column_ids in linked.items():
            schema = schemas.get(str(board_id), {})
            target_columns = {str(item["id"]): item for item in schema.get("columns") or []}
            board_name = str(schema.get("name") or f"board {board_id}")
            names = [str(target_columns.get(str(column_id), {}).get("title") or column_id) for column_id in column_ids]
            targets.append(f"{board_name}: {', '.join(names) if names else 'linked value'}")
        return "Mirrors " + ("; ".join(targets) if targets else "a linked-board value") + (f" through {', '.join(relation_names)}." if relation_names else ".")
    if column_type == "subtasks":
        target_ids = settings.get("boardIds") or []
        targets = [str(schemas.get(str(board_id), {}).get("name") or f"board {board_id}") for board_id in target_ids]
        return "Contains or exposes subitems from " + (", ".join(targets) if targets else "a subitems board") + "."
    if column_type == "formula":
        return _formula_relationship(column, master_columns)
    return "Stored directly on this Master Sheet item."


def _configured_values(column: dict[str, Any]) -> str:
    settings = _settings(column)
    labels = settings.get("labels")
    if isinstance(labels, dict):
        values = [str(value) for value in labels.values() if value]
    elif isinstance(labels, list):
        values = [str(value["name"]) for value in labels if isinstance(value, dict) and value.get("name")]
    else:
        values = []
    if not values:
        return "-"
    visible = values[:12]
    suffix = f" (+{len(values) - len(visible)} more)" if len(values) > len(visible) else ""
    return _escape("; ".join(visible) + suffix)


def _coverage(column: dict[str, Any], metadata_by_id: dict[str, dict[str, Any]]) -> str:
    meta = metadata_by_id[str(column["id"])]
    if meta.get("population_measurement", "").startswith("display_text_only"):
        return "Not reliable from text-only export"
    return f"{meta['populated_item_count']:,} ({meta['populated_percent']}%)"


def _board_overview(manifest: dict[str, Any]) -> list[str]:
    lines = ["| Board | ID | Exported records | Result |", "| --- | --- | ---: | --- |"]
    for board in manifest["boards"]:
        record_count = board.get("record_count")
        records = f"{record_count:,}" if isinstance(record_count, int) else "-"
        lines.append(
            f"| {_escape(str(board.get('name') or 'Unavailable board'))} | `{board['id']}` | "
            f"{records} | {board['status']} |"
        )
    return lines


def _write_reference(
    path: Path,
    manifest: dict[str, Any],
    master_schema: dict[str, Any],
    master_metadata: dict[str, Any],
    schemas: dict[str, dict[str, Any]],
) -> None:
    master_columns = {str(column["id"]): column for column in master_schema["columns"]}
    metadata_by_id = {str(column["id"]): column for column in master_metadata["columns"]}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for column in master_schema["columns"]:
        grouped[_category(column)].append(column)

    lines = [
        "# WCW Master Sheet Reference Guide",
        "",
        "## What This Is",
        "",
        "The Master Sheet is WCW's Monday.com operational board for referrals and their downstream workflow. Each row is a Monday item; columns are fields, statuses, links to other boards, or calculated values. This guide describes the exported schema, not a new database design.",
        "",
        "## Accuracy Audit of the Local Snapshot",
        "",
        f"- The Master Sheet export contains **{master_metadata['record_count']:,} top-level items**. Pagination completed as 36 full 500-item pages plus one 88-item page.",
        "- The exporter captured every displayed column value (`text`) and type for those items. It did not fetch item updates, attached-file contents, file assets, or nested subitems unless they exist as a separately exported related board.",
        "- Relation and mirror columns may show no displayed text even when an underlying relation exists. Their schema relationship is accurate below, but their apparent population rate must not be read as a no-link rate.",
        "- `Stage` should not be used as the historical lifecycle source of truth: almost every item remains `In intake`. The observed operating lifecycle is primarily in `Visit Status`.",
        "- This is a direct-relation export, not a recursive copy of the whole Monday CRM. It includes the Master Sheet and each board directly referenced by its relation columns.",
        "- A related board showing zero exported top-level items means this token's API query returned zero items. It does not, by itself, prove that WCW has no data in that business area.",
        "",
        "## Exported Board Surface",
        "",
        *_board_overview(manifest),
        "",
        "## How To Read the Dictionary",
        "",
        "- **Stored directly** means the value belongs to this Master Sheet item and could be written only after its business owner approves automation.",
        "- **Links** connect to another Monday board. They require a matching rule and must not be populated as free text.",
        "- **Mirrors** show a value from a linked board. They are derived, not independent source fields.",
        "- **Formulas** are calculated by Monday and are never write targets.",
        "- **Observed coverage** is based on rendered text in this snapshot. It is reliable for direct fields; it is deliberately marked unreliable for links and mirrors.",
        "",
        "## Key Interpretation Before Automation",
        "",
        "For a first intake integration, create only the approved intake row and preserve human ownership of case-manager handoff, provider choice, scheduling, visit, hold, QA, and discharge statuses. The Master Sheet has no obvious dedicated field for diagnosis, insurance, requested services, or the original PDF; WCW must decide whether these belong in Monday, DRK, or both.",
        "",
        "## Complete Column Dictionary",
        "",
    ]
    for category in sorted(grouped):
        lines.extend([f"### {category}", "", "| Column | Type | What It Represents | Relationship to Master Sheet | Observed coverage | Configured choices |", "| --- | --- | --- | --- | ---: | --- |"])
        for column in grouped[category]:
            lines.append(
                f"| {_escape(str(column['title']))} (`{column['id']}`) | `{column['type']}` | "
                f"{_escape(_field_purpose(column))} | {_escape(_relationship_summary(column, master_columns, schemas))} | "
                f"{_coverage(column, metadata_by_id)} | {_configured_values(column)} |"
            )
        lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_scenarios(path: Path, examples: list[dict[str, Any]]) -> None:
    criteria = {
        "referral_intake": "`Stage = In intake`",
        "handoff": "`Sent to CM = Yes`",
        "scheduled": "`Scheduling Complete = Yes` and `Visit Status = Scheduled`",
        "seen": "`Visit Status = Seen`",
        "on_hold": "`Visit Status = On Holds List` or `Hospitalized`",
        "discharged": "`Visit Status` is one of the discharge-prefixed values used by WCW.",
    }
    use_cases = {
        "referral_intake": "Shows the expected shape of a newly received referral before case-manager/scheduling work is automated.",
        "handoff": "Shows the downstream state after a referral has been sent to a case manager; it is a human-owned handoff example, not a V1 write target.",
        "scheduled": "Shows the fields that collectively indicate a referral was scheduled, useful for validating a future status-integration rule.",
        "seen": "Shows the operational state for a completed visit, useful for understanding reporting and lifecycle interpretation.",
        "on_hold": "Shows the operational exception path for hospitalization or an active holds list; it should remain a human workflow until rules are agreed.",
        "discharged": "Shows a discharge outcome. It is useful for understanding history and future reporting, not for deciding a discharge automatically.",
    }
    lines = [
        "# WCW Scenario Examples Guide",
        "",
        "## Purpose",
        "",
        "`scenario_examples.json` is a local, PHI-bearing companion file selected from the Master Sheet export. It provides representative real records for understanding how WCW has used its columns. This guide explains the scenarios without repeating any patient information.",
        "",
        "## Selection Method and Limits",
        "",
        "Each scenario is selected by a concrete status rule, then the exporter chooses the matching record with the most non-empty displayed fields. These are examples, not gold-standard business rules, not necessarily the most recent record, and not proof that every historical record follows the same convention.",
        "",
    ]
    for example in examples:
        scenario_id = str(example["scenario"])
        title = scenario_id.replace("_", " ").title()
        lines.extend(
            [
                f"## {title}",
                "",
                f"**Selection rule:** {criteria.get(scenario_id, 'See scenario_examples.json')}",
                "",
                f"**What it demonstrates:** {use_cases.get(scenario_id, example.get('description', 'Representative workflow state.'))}",
                "",
                f"**Export result:** {example.get('status', 'unknown')}. The selected row contains {len(example.get('fields') or {})} non-empty projected fields.",
                "",
            ]
        )
    lines.extend(
        [
            "## Safe Use",
            "",
            "Keep `scenario_examples.json` local and out of Git because it contains patient data. Use it to validate the data dictionary with authorized WCW staff, then replace representative examples with a manually approved evaluation set for testing automation behavior.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate PHI-free Master Sheet reference guides.")
    parser.add_argument("export_dir", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("."))
    args = parser.parse_args(argv)

    manifest = _read_json(args.export_dir / "manifest.json")
    board_by_id = {str(board["id"]): board for board in manifest["boards"]}
    master_entry = board_by_id[MASTER_SHEET_ID]
    master_dir = args.export_dir / str(master_entry.get("directory") or f"boards/{MASTER_SHEET_ID}")
    master_schema = _read_json(master_dir / "schema.json")
    master_metadata = _read_json(master_dir / "metadata.json")
    schemas = {
        board_id: _read_json(args.export_dir / str(board["directory"]) / "schema.json")
        for board_id, board in board_by_id.items()
        if board.get("directory") and (args.export_dir / str(board["directory"]) / "schema.json").exists()
    }
    scenarios = _read_json(args.export_dir / "scenario_examples.json")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    reference_path = args.output_dir / "WCW Master Sheet Reference Guide.md"
    scenarios_path = args.output_dir / "WCW Scenario Examples Guide.md"
    _write_reference(reference_path, manifest, master_schema, master_metadata, schemas)
    _write_scenarios(scenarios_path, scenarios)
    print(f"Wrote {reference_path}")
    print(f"Wrote {scenarios_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
