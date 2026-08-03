"""Operator-friendly CLI for Outlook referral intake and guarded Monday writes."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


# `monday.com` is a scripts directory rather than an importable package. Add the
# project src directory so this entry point works without shell-specific PYTHONPATH.
SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from master_sheet_writer import apply_master_sheet_create  # noqa: E402
from run_inbound_intake import main as run_inbound_main  # noqa: E402


DEFAULT_OUTPUT_ROOT = Path("tmp") / "inbox-runs"
LATEST_POINTER_NAME = "latest.json"


class IntakeCLIError(RuntimeError):
    pass


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the Outlook-to-Monday referral intake flow with safe defaults.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    outlook = commands.add_parser(
        "outlook",
        help="Process PDF attachments from the configured Outlook mailbox.",
    )
    write_mode = outlook.add_mutually_exclusive_group()
    write_mode.add_argument("--dry-run", action="store_true", help="Build and save a preview only (default).")
    write_mode.add_argument("--apply", action="store_true", help="Create an unblocked Master Sheet item immediately.")
    outlook.add_argument("--confirm-master-sheet-write", action="store_true")
    outlook.add_argument("--max-messages", type=int, default=1)
    outlook.add_argument("--input-mode", choices=("auto", "text", "image", "hybrid"), default="image")
    outlook.add_argument("--max-pages", type=int)
    outlook.add_argument("--monday-mode", choices=("disabled", "snapshot", "live-readonly"), default="live-readonly")
    outlook.add_argument("--monday-records-file", type=Path)
    outlook.add_argument("--agency-mode", choices=("disabled", "snapshot", "live-readonly"), default="live-readonly")
    outlook.add_argument("--agency-records-file", type=Path)
    outlook.add_argument("--include-full-row", action="store_true")
    outlook.add_argument("--config", type=Path)
    outlook.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    outlook.add_argument("--state-db", type=Path)
    outlook.add_argument("--force", action="store_true", help="Reprocess the newest PDF even if its hash was completed.")
    outlook.add_argument("--quiet", action="store_true", help="Suppress progress logs while retaining the final summary.")

    apply = commands.add_parser(
        "apply",
        help="Apply the exact preview from the latest successful dry run.",
    )
    source = apply.add_mutually_exclusive_group()
    source.add_argument("--preview", type=Path, help="Apply a specific master-sheet-preview.json file.")
    source.add_argument("--run", type=Path, help="Apply the only preview inside a specific run directory.")
    apply.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    apply.add_argument("--confirm-master-sheet-write", action="store_true", required=True)

    return parser


def _new_run_dir(output_root: Path) -> Path:
    output_root.mkdir(parents=True, exist_ok=True)
    stem = datetime.now().strftime("%Y%m%d-%H%M%S")
    candidate = output_root / stem
    suffix = 2
    while candidate.exists():
        candidate = output_root / f"{stem}-{suffix}"
        suffix += 1
    return candidate


def _run_outlook(args: argparse.Namespace) -> int:
    if args.apply and not args.confirm_master_sheet_write:
        raise IntakeCLIError("--apply requires --confirm-master-sheet-write")
    if args.max_messages < 1:
        raise IntakeCLIError("--max-messages must be at least 1")

    output_root = args.output_root.resolve()
    run_dir = _new_run_dir(output_root)
    state_db = (args.state_db or output_root / "state.sqlite").resolve()
    mode = "apply" if args.apply else "dry-run"

    delegated = [
        "--outlook-poll",
        "--max-messages",
        str(args.max_messages),
        "--input-mode",
        args.input_mode,
        "--monday-mode",
        args.monday_mode,
        "--agency-mode",
        args.agency_mode,
        "--output-dir",
        str(run_dir),
        "--state-db",
        str(state_db),
        "--master-sheet-mode",
        mode,
    ]
    if args.max_pages is not None:
        delegated.extend(("--max-pages", str(args.max_pages)))
    if args.monday_records_file is not None:
        delegated.extend(("--monday-records-file", str(args.monday_records_file)))
    if args.agency_records_file is not None:
        delegated.extend(("--agency-records-file", str(args.agency_records_file)))
    if args.include_full_row:
        delegated.append("--include-full-row")
    if args.config is not None:
        delegated.extend(("--config", str(args.config)))
    if args.force:
        delegated.append("--force")
    if not args.quiet:
        delegated.append("--verbose")
    if args.confirm_master_sheet_write:
        delegated.append("--confirm-master-sheet-write")

    print(f"[intake] source: Outlook ({args.max_messages} newest message{'s' if args.max_messages != 1 else ''})")
    print(f"[intake] mode: {mode}")
    print(f"[intake] run directory: {run_dir}")
    exit_code = run_inbound_main(delegated)

    pointer = _record_latest_run(output_root, run_dir)
    _print_run_result(pointer, output_root=output_root)
    return exit_code


def _record_latest_run(output_root: Path, run_dir: Path) -> dict[str, Any]:
    summary_path = run_dir / "run-summary.json"
    pointer: dict[str, Any] = {
        "version": 1,
        "status": "not_ready",
        "run_dir": str(run_dir.resolve()),
        "summary_path": str(summary_path.resolve()),
    }
    try:
        results = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        pointer["reason"] = f"run summary could not be read: {error}"
        return _write_pointer(output_root, pointer)

    if not isinstance(results, list) or len(results) != 1 or not isinstance(results[0], dict):
        pointer["reason"] = "the simple apply flow requires exactly one attachment result"
        return _write_pointer(output_root, pointer)

    result = results[0]
    pointer.update(
        {
            "filename": result.get("filename"),
            "attachment_sha256": result.get("attachment_sha256"),
            "created_item_id": result.get("created_item_id"),
        }
    )
    if result.get("status") != "completed":
        pointer["reason"] = str(result.get("status") or "attachment did not complete")
        return _write_pointer(output_root, pointer)

    preview_value = result.get("preview_path")
    if not isinstance(preview_value, str) or not preview_value:
        pointer["reason"] = "completed result did not contain a preview path"
        return _write_pointer(output_root, pointer)

    preview_path = _absolute_path(preview_value)
    pointer["preview_path"] = str(preview_path)
    try:
        preview = _load_json_object(preview_path, label="Master Sheet preview")
    except IntakeCLIError as error:
        pointer["reason"] = str(error)
        return _write_pointer(output_root, pointer)

    pointer["item_name"] = preview.get("item_name")
    if result.get("created_item_id"):
        pointer["status"] = "applied"
    elif result.get("master_sheet_blocked") or preview.get("blocked"):
        blockers = result.get("master_sheet_blockers") or preview.get("blockers") or []
        pointer["reason"] = "; ".join(str(blocker) for blocker in blockers) or "preview is blocked"
    else:
        pointer["status"] = "ready"
    return _write_pointer(output_root, pointer)


def _write_pointer(output_root: Path, pointer: dict[str, Any]) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / LATEST_POINTER_NAME).write_text(
        json.dumps(pointer, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return pointer


def _print_run_result(pointer: dict[str, Any], *, output_root: Path) -> None:
    status = pointer["status"]
    print(f"[intake] status: {status}")
    if pointer.get("item_name"):
        print(f"[intake] patient: {pointer['item_name']}")
    if status == "ready":
        print("[intake] no Monday item was created")
        print("[intake] next: python src/monday.com/intake.py apply --confirm-master-sheet-write")
    elif status == "applied":
        print(f"[intake] created Monday item: {pointer.get('created_item_id')}")
    else:
        print(f"[intake] not ready to apply: {pointer.get('reason', 'unknown reason')}")
    print(f"[intake] latest run metadata: {output_root / LATEST_POINTER_NAME}")


def _apply_preview(args: argparse.Namespace) -> int:
    preview_path, pointer = _select_preview(args)
    preview = _load_json_object(preview_path, label="Master Sheet preview")
    if preview.get("blocked"):
        blockers = preview.get("blockers") or []
        raise IntakeCLIError(f"preview is blocked: {'; '.join(str(value) for value in blockers)}")
    if preview.get("operation") != "create_item":
        raise IntakeCLIError("preview is not a Master Sheet create_item operation")

    result_path = preview_path.parent / "master-sheet-apply-result.json"
    if result_path.exists():
        raise IntakeCLIError(f"this preview already has an apply result: {result_path}")

    print(f"[intake] applying preview: {preview_path}")
    print(f"[intake] patient: {preview.get('item_name') or 'unknown'}")
    result = apply_master_sheet_create({**preview, "mode": "apply"})
    result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    created_item_id = result["item"]["id"]

    if pointer is not None:
        pointer["status"] = "applied"
        pointer["created_item_id"] = created_item_id
        pointer["apply_result_path"] = str(result_path.resolve())
        _write_pointer(args.output_root.resolve(), pointer)

    print(
        json.dumps(
            {
                "status": "applied",
                "item_name": preview.get("item_name"),
                "created_item_id": created_item_id,
                "apply_result": str(result_path),
            },
            indent=2,
        )
    )
    return 0


def _select_preview(args: argparse.Namespace) -> tuple[Path, dict[str, Any] | None]:
    if args.preview is not None:
        return args.preview.resolve(), None
    if args.run is not None:
        matches = list(args.run.resolve().rglob("master-sheet-preview.json"))
        if len(matches) != 1:
            raise IntakeCLIError(f"--run must contain exactly one preview; found {len(matches)}")
        return matches[0], None

    pointer_path = args.output_root.resolve() / LATEST_POINTER_NAME
    pointer = _load_json_object(pointer_path, label="latest run metadata")
    if pointer.get("status") != "ready":
        raise IntakeCLIError(
            f"latest run is not ready to apply: {pointer.get('reason') or pointer.get('status') or 'unknown status'}"
        )
    preview_value = pointer.get("preview_path")
    if not isinstance(preview_value, str) or not preview_value:
        raise IntakeCLIError("latest run metadata does not contain a preview path")
    return _absolute_path(preview_value), pointer


def _load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise IntakeCLIError(f"{label} could not be read: {path}") from error
    except json.JSONDecodeError as error:
        raise IntakeCLIError(f"{label} is not valid JSON: {path}") from error
    if not isinstance(value, dict):
        raise IntakeCLIError(f"{label} must be a JSON object: {path}")
    return value


def _absolute_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "outlook":
            return _run_outlook(args)
        return _apply_preview(args)
    except IntakeCLIError as error:
        print(f"intake: error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
