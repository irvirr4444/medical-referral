"""Render patient activity JSON files as one human-readable report per patient."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from dotenv import load_dotenv  # noqa: E402


DEFAULT_INPUT = REPO_ROOT / "output" / "activity-logs" / "patients"
DEFAULT_OUTPUT = REPO_ROOT / "output" / "activity-logs" / "patients"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help="One *.activity.json file or a directory containing patient exports.",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def text(value: Any, *, fallback: str = "—") -> str:
    if value is None or value == "":
        return fallback
    return " ".join(str(value).replace("\r", " ").replace("\n", " ").split())


def md(value: Any, *, fallback: str = "—") -> str:
    return text(value, fallback=fallback).replace("|", "\\|")


def display_date(value: Any) -> str:
    raw = text(value)
    if raw == "—":
        return raw
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return raw
    suffix = " UTC" if parsed.tzinfo is not None else ""
    return parsed.strftime("%Y-%m-%d %H:%M:%S") + suffix


def value_summary(value: Any) -> str:
    if value is None:
        return "blank"
    if not isinstance(value, dict):
        return text(value, fallback="blank")
    if not value:
        return "blank"
    label = value.get("label")
    if isinstance(label, dict) and label.get("text"):
        return text(label["text"])
    for key in ("textual_value", "text", "email", "value"):
        if value.get(key) not in (None, ""):
            return text(value[key])
    if value.get("date"):
        result = str(value["date"])
        if value.get("time"):
            result += f" {value['time']}"
        return result
    chosen = value.get("chosenValues")
    if isinstance(chosen, list):
        return ", ".join(text(item.get("name")) for item in chosen if isinstance(item, dict)) or "blank"
    people = value.get("personsAndTeams")
    if isinstance(people, list):
        return ", ".join(f"person/team {item.get('id')}" for item in people if isinstance(item, dict))
    linked = value.get("linkedPulseIds")
    if isinstance(linked, list):
        return ", ".join(f"linked item {item.get('linkedPulseId')}" for item in linked if isinstance(item, dict))
    if value.get("running") is not None:
        return f"running={value.get('running')}, duration={value.get('duration', 0)}"
    return text(json.dumps(value, ensure_ascii=False, sort_keys=True))


def resolve_monday_users(payload: dict[str, Any]) -> dict[str, str]:
    patients = [payload.get("patient") or {}]
    ids = sorted(
        {
            str(event.get("actor_user_id"))
            for patient in patients
            for event in ((patient.get("monday") or {}).get("activity") or [])
            if str(event.get("actor_user_id") or "").isdigit() and int(event["actor_user_id"]) > 0
        }
    )
    users = {"-4": "Monday automation/system"}
    if not ids:
        return users
    load_dotenv(REPO_ROOT / ".env")
    if not os.getenv("MONDAY_DOT_COM_API_KEY"):
        return users
    try:
        from referral_pipeline.integrations.monday.transport import monday_graphql

        response = monday_graphql("query($ids:[ID!]){users(ids:$ids){id name}}", variables={"ids": ids})
        users.update(
            {str(user["id"]): text(user.get("name")) for user in (response.get("data") or {}).get("users", [])}
        )
    except Exception:
        pass
    return users


def monday_description(event: dict[str, Any], users: dict[str, str]) -> tuple[str, str, str]:
    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    actor_id = str(event.get("actor_user_id") or "")
    actor = users.get(actor_id, f"Monday user {actor_id}" if actor_id else "Unknown actor")
    kind = event.get("event")
    if kind == "create_pulse":
        return "Item created", f"Created in {text(data.get('group_name'), fallback='the board')}", actor
    if kind == "move_pulse_from_group":
        source = (data.get("source_group") or {}).get("title")
        destination = (data.get("dest_group") or {}).get("title")
        return "Board group changed", f"{text(source)} → {text(destination)}", actor
    if kind == "subscribe":
        return "Subscriber added", f"Subscribed Monday user {text(data.get('subscribed_id'))}", actor
    if kind == "update_column_value":
        field = text(data.get("column_title"), fallback="Unnamed column")
        previous = value_summary(data.get("previous_value"))
        current = data.get("textual_value")
        current = text(current) if current not in (None, "") else value_summary(data.get("value"))
        return field, f"{previous} → {current}", actor
    return text(kind, fallback="Monday activity"), text(data), actor


def report(payload: dict[str, Any]) -> str:
    users = resolve_monday_users(payload)
    patient = payload.get("patient") or {}
    sample = patient.get("sample") or {}
    monday = patient.get("monday") or {}
    drk = patient.get("drk") or {}
    pipeline = drk.get("pipeline_current") or {}
    lines = [
        f"# Patient Activity Report — {text(sample.get('name'))}",
        "",
        "> **Restricted:** This report contains real PHI and operational history. Keep it local, do not commit it, and do not use its identifiers as synthetic-data seeds.",
        "",
        f"Generated from the machine-readable export at {display_date(payload.get('generated_at_utc'))}.",
        "",
        "## Overview",
        "",
        "| Patient | Monday events | DRK communications | DRK encounters | DRK documents | Current DRK stage |",
        "|---|---:|---:|---:|---:|---|",
    ]
    lines.append(
        "| "
        + " | ".join(
            (
                md(sample.get("name")),
                str(monday.get("activity_count", 0)),
                str(drk.get("communications_total", 0)),
                str(drk.get("encounters_total", 0)),
                str(drk.get("document_uploads_total", 0)),
                md(pipeline.get("currentStageName")),
            )
        )
        + " |"
    )

    lines.extend(
            [
                "",
                f"## {text(sample.get('name'))}",
                "",
                f"- Source PDF: `{text(sample.get('source_pdf'))}`",
                f"- Monday item: `{text(monday.get('item_id'))}`",
                f"- DRK patient: `{text(drk.get('patient_id'))}`",
                f"- Current DRK stage: **{text(pipeline.get('currentStageName'))}**",
                f"- Previous DRK stage: {text(pipeline.get('previousStageName'))}",
                f"- DRK status: {text(pipeline.get('intakeStatusName'))}; ACT: {text(pipeline.get('actStatusName'))}",
                "",
                "### Monday activity",
                "",
                "| Date | Activity | Change | Actor |",
                "|---|---|---|---|",
            ]
    )
    for event in monday.get("activity") or []:
        activity, change, actor = monday_description(event, users)
        lines.append(
            f"| {md(display_date(event.get('timestamp_utc')))} | {md(activity)} | {md(change)} | {md(actor)} |"
        )

    lines.extend(["", "### DRK admission and pipeline history", ""])
    admission_history = drk.get("admission_history") or []
    if not admission_history:
        lines.append("No admission-status events were returned.")
    for event in admission_history:
        lines.extend(
                [
                    f"- **{display_date(event.get('createdDate'))} — {text(event.get('eventType'), fallback='Admission event')}**",
                    f"  - Status: {text(event.get('fromStatusDisplayName'))} → {text(event.get('toStatusDisplayName'))}",
                    f"  - Recorded by: {text(event.get('createdByUserName'))}",
                    f"  - Discharge date/reason: {display_date(event.get('dischargeDate'))}; {text(event.get('dischargeStatusName'))}",
                ]
        )
    for stage in drk.get("pipeline_timeline") or []:
        lines.extend(
                [
                    f"- **Pipeline stage — {text(stage.get('stageName'))}: {text(stage.get('status'))}**",
                    f"  - Entered: {display_date(stage.get('enteredDate'))}; completed: {display_date(stage.get('completedDate'))}",
                    f"  - Completed by: {text(stage.get('completedByUserName'))}; days in stage: {text(stage.get('daysInStage'))}",
                ]
        )

    lines.extend(["", "### DRK communications", ""])
    communications = drk.get("communications") or []
    if not communications:
        lines.append("No communications were returned.")
    for item in communications:
        direction = "Inbound" if item.get("isInbound") else "Outbound"
        lines.extend(
                [
                    f"- **{display_date(item.get('timestamp'))} — {text(item.get('communicationType'), fallback='Communication')}**",
                    f"  - {direction} {text(item.get('contactMethod'))}; status: {text(item.get('status'))}",
                    f"  - User/department: {text(item.get('userName'))} / {text(item.get('department'))}",
                ]
        )
        if item.get("subject"):
            lines.append(f"  - Subject: {text(item.get('subject'))}")
        if item.get("notes"):
            lines.append(f"  - Notes: {text(item.get('notes'))}")

    lines.extend(["", "### DRK encounters", ""])
    encounters = drk.get("encounters") or []
    if not encounters:
        lines.append("No encounters were returned.")
    for item in encounters:
        lines.extend(
                [
                    f"- **{display_date(item.get('encounterDate'))} — {text(item.get('serviceType'), fallback='Encounter')}**",
                    f"  - Status: {text(item.get('status'))}; signed: {'Yes' if item.get('isSigned') else 'No'}",
                    f"  - Provider: {text(item.get('providerName'))}",
                    f"  - Created by: {text(item.get('createdByName'))} ({text(item.get('createdByRole'))})",
                ]
        )

    lines.extend(["", "### DRK document activity", ""])
    uploads = drk.get("document_uploads") or []
    if not uploads:
        lines.append("No document uploads were returned.")
    for item in uploads:
        lines.extend(
                [
                    f"- **{display_date(item.get('uploadDate'))} — {text(item.get('category'), fallback='Document')}**",
                    f"  - {text(item.get('description') or item.get('fileName'))}",
                    f"  - Uploaded by: {text(item.get('uploadedBy'))}; type: {text(item.get('fileType'))}",
                ]
        )

    lines.extend(
        [
            "",
            "## Interpretation notes",
            "",
            "- Monday timestamps are normalized to UTC. DRK timestamps are displayed exactly as returned; DRK does not provide a timezone on these fields.",
            "- Monday automation/system actions appear separately from named users.",
            "- Empty dates in the DRK pipeline are source-system omissions, not exporter failures.",
            "- Use this report to learn event categories, sequencing, phrasing, and realistic activity density. Replace every real identifier and free-text detail when generating synthetic data.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    inputs = sorted(args.input.glob("*.activity.json")) if args.input.is_dir() else [args.input]
    if not inputs:
        raise RuntimeError(f"No patient activity JSON files found at {args.input}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for input_path in inputs:
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        output_path = args.output_dir / input_path.name.replace(".activity.json", ".report.md")
        output_path.write_text(report(payload), encoding="utf-8")
        print(f"Wrote {output_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
