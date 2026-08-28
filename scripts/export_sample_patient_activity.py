"""Export read-only Monday and DRK activity into one file per reviewed patient.

The generated JSON contains real operational data and may contain PHI. It is
written beneath ``output/`` (gitignored) and must not be committed.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
import unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
MONDAY_ROOT = SRC_ROOT / "monday.com"
for path in (SRC_ROOT, MONDAY_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from dotenv import load_dotenv  # noqa: E402

from drk_emr.common.browser import DASHBOARD_PATH, emr_root  # noqa: E402
from drk_emr.common.patient_search import (  # noqa: E402
    search_patients_on_dashboard,
    select_search_candidate,
)
from drk_emr.live_reader import DrkLiveReaderConfig, DrkPatientReader  # noqa: E402
from master_sheet_reader import (  # noqa: E402
    fetch_items_by_column_value,
    fetch_items_by_name_search,
    find_patients,
)
from monday_api import monday_graphql  # noqa: E402


BOARD_ID = "5815942462"
MONDAY_ACTIVITY_QUERY = """
query($boardIds: [ID!], $itemIds: [ID!], $limit: Int!, $page: Int!) {
  boards(ids: $boardIds) {
    id
    activity_logs(item_ids: $itemIds, limit: $limit, page: $page) {
      id
      event
      entity
      data
      user_id
      created_at
    }
  }
}
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold-dir", type=Path, default=REPO_ROOT / "eval" / "gold")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "output" / "activity-logs" / "patients",
    )
    parser.add_argument(
        "--patient",
        action="append",
        default=[],
        help="Export only this reviewed patient; repeat to select more than one.",
    )
    parser.add_argument("--board-id", default=BOARD_ID)
    parser.add_argument(
        "--monday-only",
        action="store_true",
        help="Refresh Monday activity in an existing export without reopening DRK.",
    )
    return parser.parse_args()


def load_sample_identities(gold_dir: Path) -> list[dict[str, Any]]:
    identities: list[dict[str, Any]] = []
    for path in sorted(gold_dir.glob("*.gold.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        record = payload.get("record") or {}
        identities.append(
            {
                "source_gold": str(path.relative_to(REPO_ROOT)),
                "source_pdf": record.get("source_file") or payload.get("pdf_name"),
                "name": record.get("patient_name"),
                "date_of_birth": record.get("patient_dob"),
                "phone": record.get("patient_phone"),
                "mrn": record.get("patient_mrn"),
            }
        )
    if len(identities) != 7:
        raise RuntimeError(f"Expected 7 reviewed sample identities, found {len(identities)}")
    return identities


def patient_slug(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", normalized.casefold()).strip("-") or "patient"


def select_identities(
    identities: list[dict[str, Any]],
    requested: list[str],
) -> list[dict[str, Any]]:
    if not requested:
        return identities
    selected: list[dict[str, Any]] = []
    for query in requested:
        query_terms = set(patient_slug(query).split("-"))
        matches = [
            identity
            for identity in identities
            if query_terms == set(patient_slug(str(identity.get("name") or "")).split("-"))
            or patient_slug(query) == patient_slug(str(identity.get("name") or ""))
        ]
        if len(matches) != 1:
            names = ", ".join(str(item.get("name")) for item in identities)
            raise RuntimeError(
                f"--patient {query!r} matched {len(matches)} reviewed patients; choose one of: {names}"
            )
        if matches[0] not in selected:
            selected.append(matches[0])
    return selected


def output_path(output_dir: Path, identity: dict[str, Any]) -> Path:
    return output_dir / f"{patient_slug(str(identity['name']))}.activity.json"


def monday_activity(identity: dict[str, Any], board_id: str) -> dict[str, Any]:
    candidates = list(fetch_items_by_name_search(name=identity["name"], board_id=board_id).items)
    matches = find_patients(candidates, name=identity["name"])
    if len(matches) != 1 and identity.get("date_of_birth"):
        dob_value = datetime.strptime(identity["date_of_birth"], "%m/%d/%Y").strftime("%Y-%m-%d")
        dob_candidates = list(
            fetch_items_by_column_value(
                field="dob",
                value=dob_value,
                board_id=board_id,
                max_items=100,
            ).items
        )
        combined = {str(item.get("id")): item for item in [*candidates, *dob_candidates]}
        ranked = sorted(
            (
                (_name_similarity(identity["name"], str(item.get("name") or "")), item)
                for item in combined.values()
            ),
            key=lambda pair: pair[0],
            reverse=True,
        )
        matches = [ranked[0][1]] if ranked and ranked[0][0] >= 0.72 else []
    if len(matches) != 1:
        return {
            "status": "not_uniquely_matched",
            "candidate_count": len(candidates),
            "match_count": len(matches),
        }

    item = matches[0]
    logs: list[dict[str, Any]] = []
    for page in range(1, 11):
        response = monday_graphql(
            MONDAY_ACTIVITY_QUERY,
            variables={
                "boardIds": [str(board_id)],
                "itemIds": [str(item["id"])],
                "limit": 1000,
                "page": page,
            },
        )
        boards = (response.get("data") or {}).get("boards") or []
        batch = (boards[0].get("activity_logs") if boards else []) or []
        logs.extend(batch)
        if len(batch) < 1000:
            break

    normalized = []
    for log in reversed(logs):
        raw_data = log.get("data")
        try:
            data = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
        except json.JSONDecodeError:
            data = raw_data
        normalized.append(
            {
                "id": log.get("id"),
                "timestamp_utc": monday_timestamp(log.get("created_at")),
                "event": log.get("event"),
                "entity": log.get("entity"),
                "actor_user_id": log.get("user_id"),
                "data": data,
            }
        )
    return {
        "status": "matched",
        "board_id": str(board_id),
        "item_id": str(item["id"]),
        "item_name": item.get("name"),
        "activity_count": len(normalized),
        "activity": normalized,
    }


def _name_similarity(left: str, right: str) -> float:
    def canonical(value: str) -> str:
        text = " ".join(value.casefold().replace("-", " ").split())
        if "," in text:
            family, given = [part.strip() for part in text.split(",", 1)]
            text = f"{given} {family}"
        return "".join(char for char in text if char.isalnum() or char == " ")

    return SequenceMatcher(None, canonical(left), canonical(right)).ratio()


def monday_timestamp(value: Any) -> str | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return str(value) if value is not None else None
    if number > 10**15:
        seconds = number / 10_000_000
    elif number > 10**12:
        seconds = number / 1000
    else:
        seconds = number
    return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat()


def card_payloads(cards: dict[str, dict[str, Any]], card_name: str) -> list[Any]:
    payloads: list[Any] = []
    for record in (cards.get(card_name) or {}).get("records") or []:
        body = record.get("business_data")
        if isinstance(body, dict) and "data" in body:
            payloads.append(body.get("data"))
        elif body is not None:
            payloads.append(body)
    return payloads


def first_mapping(payloads: list[Any]) -> dict[str, Any]:
    return next((item for item in payloads if isinstance(item, dict)), {})


def drk_activity(
    reader: DrkPatientReader,
    identity: dict[str, Any],
) -> dict[str, Any]:
    assert reader.driver is not None
    reader.driver.get(f"{emr_root(reader.config.emr_url)}{DASHBOARD_PATH}")
    snapshot = search_patients_on_dashboard(reader.driver, identity["name"])
    match = select_search_candidate(
        snapshot.candidates,
        name=identity["name"],
        date_of_birth=identity.get("date_of_birth"),
        phone=identity.get("phone"),
        mrn=identity.get("mrn"),
    )
    if match is None or not match.patient_id:
        return {
            "status": "not_uniquely_matched",
            "candidate_count": len(snapshot.candidates),
            "search_error": snapshot.error,
        }

    capture = reader.read_patient(match.patient_id)
    cards = capture.cards
    admission = first_mapping(card_payloads(cards, "admission"))
    communications = first_mapping(card_payloads(cards, "communications"))
    encounters = first_mapping(card_payloads(cards, "encounters"))
    scans = first_mapping(card_payloads(cards, "custom_scans"))
    pipeline = first_mapping(card_payloads(cards, "pipeline"))
    quick_notes = card_payloads(cards, "quick_notes")

    return {
        "status": "matched",
        "patient_id": capture.patient_id,
        "observed_at_utc": capture.observed_at.isoformat(),
        "admission_history": admission.get("admissionHistory") or [],
        "communications": communications.get("communications") or [],
        "communications_total": communications.get("totalCount", 0),
        "encounters": encounters.get("encounters") or [],
        "encounters_total": encounters.get("totalCount", 0),
        "document_uploads": [
            {key: value for key, value in upload.items() if key != "fileUrl"}
            for upload in (scans.get("scans") or [])
            if isinstance(upload, dict)
        ],
        "document_uploads_total": scans.get("totalCount", 0),
        "pipeline_current": pipeline,
        "pipeline_timeline": pipeline.get("timelineSteps") or [],
        "quick_notes": quick_notes,
    }


def sanitize_export(result: dict[str, Any]) -> None:
    """Remove non-activity payloads and direct document URLs from stored exports."""
    patient = result.get("patient") or {}
    drk = patient.get("drk") or {}
    drk.pop("insurance_and_eligibility", None)
    for upload in drk.get("document_uploads") or []:
        if isinstance(upload, dict):
            upload.pop("fileUrl", None)


def new_export(identity: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "classification": "Contains real PHI; local evaluation use only; do not commit",
        "source_systems": ["monday.com", "DRK EMR"],
        "patient": {"sample": identity, "monday": None, "drk": None},
    }


def write_export(result: dict[str, Any], path: Path) -> None:
    sanitize_export(result)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {path.resolve()}", flush=True)


def main() -> int:
    args = parse_args()
    load_dotenv(REPO_ROOT / ".env")
    identities = select_identities(load_sample_identities(args.gold_dir), args.patient)
    total = len(identities)
    results: list[dict[str, Any]] = []
    if args.monday_only:
        for identity in identities:
            path = output_path(args.output_dir, identity)
            if not path.exists():
                raise RuntimeError(f"--monday-only requires an existing patient export: {path}")
            result = json.loads(path.read_text(encoding="utf-8"))
            result["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
            results.append(result)
    else:
        results = [new_export(identity) for identity in identities]

    for index, (identity, result) in enumerate(zip(identities, results), start=1):
        patient = result["patient"]
        print(f"[{index}/{total}] Monday: {identity['name']}", flush=True)
        patient["monday"] = monday_activity(identity, args.board_id)
        if args.monday_only:
            write_export(result, output_path(args.output_dir, identity))
        else:
            # Persist Monday immediately so a later DRK/browser failure does not
            # discard already completed API work for this patient.
            write_export(result, output_path(args.output_dir, identity))

    if not args.monday_only:
        profile_parent = REPO_ROOT / "tmp"
        profile_parent.mkdir(parents=True, exist_ok=True)
        profile_dir = Path(tempfile.mkdtemp(prefix="drk-seven-activity-", dir=profile_parent))
        try:
            config = DrkLiveReaderConfig.from_environment(profile_dir=profile_dir)
            with DrkPatientReader(config) as reader:
                for index, (identity, result) in enumerate(zip(identities, results), start=1):
                    patient = result["patient"]
                    identity = patient["sample"]
                    print(f"[{index}/{total}] DRK: {identity['name']}", flush=True)
                    try:
                        patient["drk"] = drk_activity(reader, identity)
                    except Exception as exc:  # preserve other patients when one lookup fails
                        patient["drk"] = {
                            "status": "error",
                            "error_type": type(exc).__name__,
                            "error": str(exc),
                        }
                    write_export(result, output_path(args.output_dir, identity))
        finally:
            shutil.rmtree(profile_dir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
