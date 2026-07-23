"""Create a local workflow map and real-record examples from a Master Sheet export."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


MASTER_SHEET_ID = "5815942462"
EXAMPLE_FIELDS = (
    "deal_stage",
    "date12",
    "phone",
    "location",
    "date7",
    "status_1__1",
    "text6__1",
    "text41__1",
    "email61__1",
    "status7__1",
    "time_sent_to_cm__1",
    "status__1",
    "status3__1",
    "date9__1",
    "status0__1",
    "status5__1",
    "color_mkq3gga",
    "text00__1",
    "label99",
    "color_mm1mssvv",
)

SCENARIOS = (
    ("referral_intake", "New referral awaiting intake", {"deal_stage": {"In intake"}}),
    ("handoff", "Referral handed to a case manager", {"status7__1": {"Yes"}}),
    ("scheduled", "Referral scheduled", {"status0__1": {"Yes"}, "status5__1": {"Scheduled"}}),
    ("seen", "Visit completed", {"status5__1": {"Seen"}}),
    ("on_hold", "Patient temporarily on hold", {"status5__1": {"On Holds List", "Hospitalized"}}),
    ("discharged", "Patient discharged", {"status5__1": {"DC - EXISTING PTS", "DC - NEW REFERRALS", "DC - ON HOLDS", "INACTIVE/DC'D", "Immediate DC", "DC - wx healed", "DC -Declined Service"}}),
)

FLOW_SECTIONS = (
    (
        "Referral intake",
        "Create the patient referral and capture facts received in the PDF.",
        ("name", "date12", "phone", "location", "date7", "status_1__1", "text6__1", "text41__1", "email61__1", "deal_stage"),
    ),
    (
        "Handoff and assignment",
        "Record that the referral was sent and who owns the next action.",
        ("deal_owner", "status7__1", "time_sent_to_cm__1", "status63", "date24", "people0", "status89", "date5__1"),
    ),
    (
        "Provider selection and scheduling",
        "Track contact, provider handoff, appointment, and scheduling outcome.",
        ("status__1", "status3__1", "connect_boards7", "date9__1", "status0__1", "status5__1", "color_mkq3gga", "text00__1"),
    ),
    (
        "Escalation and holds",
        "Capture exceptions that require leadership, QA, or follow-up.",
        ("label99", "date10", "color_mkxwsx63", "text81__1", "date4"),
    ),
    (
        "Visit and discharge",
        "Track the outcome and the reason a patient leaves the active workflow.",
        ("status5__1", "status72", "status69", "color_mm1mssvv", "dropdown_mm1t7rd3"),
    ),
)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _column_values(item: dict[str, Any]) -> dict[str, str]:
    return {
        str(value["id"]): str(value.get("text") or "")
        for value in item.get("column_values") or []
    }


def _matches(values: dict[str, str], criteria: dict[str, set[str]]) -> bool:
    return all(values.get(column_id) in allowed for column_id, allowed in criteria.items())


def _best_example(items: list[dict[str, Any]], criteria: dict[str, set[str]]) -> dict[str, Any] | None:
    matches = [item for item in items if _matches(_column_values(item), criteria)]
    if not matches:
        return None
    return max(matches, key=lambda item: sum(bool(value) for value in _column_values(item).values()))


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _master_sheet_directory(export_dir: Path) -> Path:
    manifest = _read_json(export_dir / "manifest.json")
    board = next(board for board in manifest["boards"] if str(board["id"]) == MASTER_SHEET_ID)
    return export_dir / str(board.get("directory") or f"boards/{MASTER_SHEET_ID}")


def _flow_report(
    column_by_id: dict[str, dict[str, Any]],
    flow_path: Path,
    stage_counts: dict[str, int],
    visit_status_counts: dict[str, int],
) -> str:
    lines = [
        "# Master Sheet Workflow Map",
        "",
        f"Source workflow: `{flow_path.name}`. This report maps its stages to the exported Master Sheet schema.",
        "",
        "## Intake Automation Boundary",
        "",
        "The current convention appears to create a record in `Working pipeline`, set `Stage` to `In intake`, and write only PDF-derived fields. It must not set handoff, scheduling, visit, or discharge outcomes until WCW confirms ownership.",
        "",
        "## Observed Lifecycle Signal",
        "",
        f"`Stage` is not a reliable historical lifecycle signal in this snapshot: `In intake` appears on {stage_counts.get('In intake', 0):,} rows. The populated operating state is `Visit Status`, including `Seen` ({visit_status_counts.get('Seen', 0):,}), `On Holds List` ({visit_status_counts.get('On Holds List', 0):,}), and discharge-prefixed statuses. Treat `Stage` as an intake marker until WCW confirms otherwise.",
        "",
        "The Master Sheet does not have dedicated fields for diagnosis, insurance, requested services, or the source PDF. Those need a confirmed destination before a production integration can preserve them.",
        "",
    ]
    for title, purpose, column_ids in FLOW_SECTIONS:
        lines.extend([f"## {title}", "", purpose, "", "| Column | Type | Population | Automation role |", "| --- | --- | ---: | --- |"])
        for column_id in column_ids:
            column = column_by_id.get(column_id)
            if column is None:
                lines.append(f"| `{column_id}` | Missing | - | Needs confirmation |")
                continue
            lines.append(
                f"| `{column['title']}` (`{column_id}`) | {column['type']} | "
                f"{column['populated_percent']}% | {column['automation_classification']} |"
            )
        lines.append("")
    lines.extend(
        [
            "## Relation Dependencies",
            "",
            "Relations should be populated only after matching logic is agreed. The export records their target board IDs in each board's `metadata.json`; they are not safe free-text fields.",
            "",
            "## Data Quality Signal",
            "",
            "Several similarly named low-population fields exist alongside the populated workflow fields. Treat column IDs, not titles alone, as the integration contract and validate a small set of current records with WCW before writing production data.",
        ]
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze an existing Master Sheet export.")
    parser.add_argument("export_dir", type=Path)
    parser.add_argument("--flow-file", type=Path, default=Path("Flow written down and questions.md"))
    args = parser.parse_args(argv)

    board_dir = _master_sheet_directory(args.export_dir)
    metadata = _read_json(board_dir / "metadata.json")
    records = _read_json(board_dir / "records.json")["items"]
    columns = {str(column["id"]): column for column in metadata["columns"]}

    examples = []
    for scenario_id, description, criteria in SCENARIOS:
        item = _best_example(records, criteria)
        if item is None:
            examples.append({"scenario": scenario_id, "description": description, "status": "no matching record found"})
            continue
        values = _column_values(item)
        examples.append(
            {
                "scenario": scenario_id,
                "description": description,
                "status": "matched",
                "item": {"id": item["id"], "name": item["name"], "group": item.get("group")},
                "fields": {
                    columns[column_id]["title"]: values[column_id]
                    for column_id in EXAMPLE_FIELDS
                    if values.get(column_id)
                },
            }
        )

    all_values = [_column_values(item) for item in records]
    stage_counts: dict[str, int] = {}
    visit_status_counts: dict[str, int] = {}
    for values in all_values:
        stage = values.get("deal_stage", "")
        visit_status = values.get("status5__1", "")
        stage_counts[stage] = stage_counts.get(stage, 0) + 1
        visit_status_counts[visit_status] = visit_status_counts.get(visit_status, 0) + 1

    _write_json(args.export_dir / "scenario_examples.json", examples)
    (args.export_dir / "flow_to_monday_map.md").write_text(
        _flow_report(columns, args.flow_file, stage_counts, visit_status_counts),
        encoding="utf-8",
    )
    print(f"Wrote {args.export_dir / 'flow_to_monday_map.md'}")
    print(f"Wrote {args.export_dir / 'scenario_examples.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
