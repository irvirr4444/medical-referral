"""Create patient-centric journey JSON from saved Monday.com and DRK pulls.

The source files are the complete internal exports produced by
``export_sample_patient_activity.py``.  This script deliberately ignores the
reviewed-sample section and flattens both operational systems into a direct
patient object. Output files contain real PHI, live beneath ``output/``
(gitignored), and must not be committed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=REPO_ROOT / "output" / "activity-logs" / "patients",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "output" / "activity-logs" / "monday-patients",
    )
    return parser.parse_args()


def meaningful_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned if cleaned and cleaned != "-" else None


def display_value(value: Any, textual_value: Any = None) -> Any:
    """Prefer Monday's human-readable value without discarding raw structure."""
    text = meaningful_text(textual_value)
    if text is not None:
        return text
    if not isinstance(value, dict):
        return value

    label = value.get("label")
    if isinstance(label, dict) and meaningful_text(label.get("text")):
        return label["text"].strip()

    date = meaningful_text(value.get("date"))
    time = meaningful_text(value.get("time"))
    if date:
        return f"{date}T{time}" if time else date

    for key in ("text", "email", "value", "name"):
        candidate = value.get(key)
        if candidate not in (None, "", {}, []):
            return candidate

    return value


def patient_date_of_birth(activity: list[dict[str, Any]]) -> Any:
    dob = None
    for event in activity:
        data = event.get("data") or {}
        if data.get("column_title") == "Patient DoB":
            dob = display_value(data.get("value"), data.get("textual_value"))
    return dob


def normalize_event(event: dict[str, Any]) -> dict[str, Any]:
    data = event.get("data") or {}
    event_name = event.get("event")
    normalized: dict[str, Any] = {
        "timestamp": event.get("timestamp_utc"),
        "action": event_name,
    }

    if event_name == "update_column_value":
        normalized.update(
            {
                "column": data.get("column_title") or data.get("column_id"),
                "column_type": data.get("column_type"),
                "previous_value": display_value(data.get("previous_value")),
                "value": display_value(data.get("value"), data.get("textual_value")),
            }
        )
    elif event_name == "create_pulse":
        normalized["action"] = "patient_created"
        normalized["group"] = data.get("group_name")
    elif event_name == "move_pulse_from_group":
        normalized["action"] = "patient_moved"
        normalized["from_group"] = data.get("source_group_name") or data.get("from_group_name")
        normalized["to_group"] = data.get("dest_group_name") or data.get("to_group_name")
    else:
        details = {
            key: value
            for key, value in data.items()
            if key
            not in {
                "board_id",
                "parent_board_id",
                "pulse_id",
                "parent_item_id",
                "pulse_name",
            }
        }
        if details:
            normalized["details"] = details

    if event.get("actor_user_id") is not None:
        normalized["actor_user_id"] = event["actor_user_id"]
    return {key: value for key, value in normalized.items() if value is not None}


def remove_redundant_patient_ids(value: Any) -> Any:
    """Remove repeated DRK patient identifiers from nested patient-owned data."""
    if isinstance(value, dict):
        return {
            key: remove_redundant_patient_ids(item)
            for key, item in value.items()
            if key not in {"patientId", "patient_id"}
        }
    if isinstance(value, list):
        return [remove_redundant_patient_ids(item) for item in value]
    return value


def convert(path: Path) -> dict[str, Any]:
    source = json.loads(path.read_text(encoding="utf-8"))
    source_patient = source.get("patient") or {}
    monday = source_patient.get("monday") or {}
    drk = source_patient.get("drk") or {}
    if monday.get("status") != "matched":
        raise RuntimeError(f"Monday patient was not matched in {path}")
    if drk.get("status") != "matched":
        raise RuntimeError(f"DRK patient was not matched in {path}")

    activity = monday.get("activity") or []
    patient: dict[str, Any] = {
        "name": monday.get("item_name"),
        "date_of_birth": patient_date_of_birth(activity),
        "activities": [normalize_event(event) for event in activity],
        "admission_history": drk.get("admission_history") or [],
        "communications": drk.get("communications") or [],
        "encounters": drk.get("encounters") or [],
        "document_uploads": drk.get("document_uploads") or [],
        "pipeline": drk.get("pipeline_current") or {},
        "pipeline_timeline": drk.get("pipeline_timeline") or [],
        "quick_notes": drk.get("quick_notes") or [],
    }
    return remove_redundant_patient_ids(
        {key: value for key, value in patient.items() if value is not None}
    )


def main() -> int:
    args = parse_args()
    paths = sorted(args.input_dir.glob("*.activity.json"))
    if not paths:
        raise RuntimeError(f"No patient activity exports found in {args.input_dir}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for path in paths:
        patient = convert(path)
        destination = args.output_dir / path.name
        destination.write_text(
            json.dumps(patient, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(
            f"Wrote {destination.resolve()} "
            f"({len(patient['activities'])} activities, "
            f"{len(patient['communications'])} communications, "
            f"{len(patient['encounters'])} encounters)",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
