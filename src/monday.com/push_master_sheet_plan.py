"""Dry-run-first creator for WCW Master Sheet intake plans."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from referral_pipeline.integrations.monday.agency_lookup import (
    find_agency_matches_from_snapshot,
    find_agency_matches_live,
)
from referral_pipeline.integrations.monday.master_sheet_writer import (
    apply_master_sheet_create,
    build_master_sheet_create_preview,
)
from referral_pipeline.integrations.monday.write_config import load_master_sheet_write_config


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a WCW Master Sheet item from an approved intake plan.")
    parser.add_argument("--plan", required=True, type=Path, help="Action-plan JSON from plan_referral_intake.py")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).with_name("master_sheet_write_config.example.json"),
        help="Master Sheet target mapping JSON.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Write a preview only (default; no Monday call).")
    mode.add_argument("--apply", action="store_true", help="Create an unblocked item in Monday.")
    parser.add_argument(
        "--confirm-master-sheet-write",
        action="store_true",
        help="Required with --apply; confirms an intended production-board create.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("tmp") / "master-sheet-write-previews",
        help="Local output directory (default is ignored by Git and may contain PHI).",
    )
    parser.add_argument(
        "--agency-mode",
        choices=("disabled", "snapshot", "live-readonly"),
        default="disabled",
        help="Optional exact agency lookup for the Referring Agency relation. Never writes during lookup.",
    )
    parser.add_argument("--agency-records-file", type=Path, help="Accounts-board records.json required for --agency-mode snapshot.")
    return parser.parse_args(argv)


def _load_plan(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except OSError as error:
        raise RuntimeError(f"Could not read intake plan: {path}") from error
    except json.JSONDecodeError as error:
        raise RuntimeError(f"Intake plan is not valid JSON: {path}") from error
    if not isinstance(payload, dict):
        raise RuntimeError(f"Intake plan must be a JSON object: {path}")
    return payload


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.apply and not args.confirm_master_sheet_write:
        raise ValueError("--apply requires --confirm-master-sheet-write")
    plan = _load_plan(args.plan)
    config = load_master_sheet_write_config(args.config)
    agency_matches = _agency_matches(args, plan, accounts_board_id=config.accounts_board_id)
    preview = build_master_sheet_create_preview(
        plan,
        config=config,
        agency_matches=agency_matches,
    )
    preview["mode"] = "apply" if args.apply else "dry-run"

    args.output_dir.mkdir(parents=True, exist_ok=True)
    preview_path = args.output_dir / f"{args.plan.stem}.master-sheet-write.json"
    preview_path.write_text(json.dumps(preview, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    result = None
    if args.apply:
        result = apply_master_sheet_create(preview)
    print(
        json.dumps(
            {
                "mode": preview["mode"],
                "blocked": preview["blocked"],
                "blockers": preview["blockers"],
                "mapped_column_count": len(preview["column_values"]),
                "mapping_note_count": len(preview["mapping_notes"]),
                "agency_match_count": len(agency_matches),
                "post_create_action_count": len(preview["post_create_actions"]),
                "written_preview": str(preview_path),
                "created_item_id": None if result is None else result["item"]["id"],
            },
            indent=2,
        )
    )
    return 0


def _agency_matches(args: argparse.Namespace, plan: dict[str, Any], *, accounts_board_id: str | None) -> list[dict[str, str]]:
    referral = plan.get("referral") or {}
    facility = referral.get("referring_facility")
    if args.agency_mode == "disabled" or not facility:
        return []
    if args.agency_mode == "snapshot":
        if args.agency_records_file is None:
            raise ValueError("--agency-records-file is required when --agency-mode snapshot")
        return find_agency_matches_from_snapshot(facility, records_file=args.agency_records_file)
    if not accounts_board_id:
        raise ValueError("The Master Sheet config needs agency_relation.accounts_board_id for live agency lookup")
    return find_agency_matches_live(facility, board_id=accounts_board_id)

if __name__ == "__main__":
    raise SystemExit(main())
