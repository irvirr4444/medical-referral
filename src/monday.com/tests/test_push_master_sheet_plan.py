from __future__ import annotations

import json

from push_master_sheet_plan import main


def test_cli_dry_run_writes_preview_without_monday_call(tmp_path, capsys) -> None:
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        json.dumps(
            {
                "outcome": "ready_for_human_approval",
                "monday_duplicate_check": {"status": "no_candidates_found"},
                "referral": {
                    "patient_name": "Example, Patient",
                    "patient_dob": "01/02/1980",
                    "patient_phone": "555-555-0100",
                },
            }
        )
    )
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "board_id": 1,
                "group_id": "working",
                "stage_label": "In intake",
                "phone_country_code": "US",
                "columns": {"patient_dob": "dob", "patient_phone": "phone", "stage": "stage"},
                "writes": {"stage": True},
            }
        )
    )

    assert main(["--plan", str(plan_path), "--config", str(config_path), "--output-dir", str(tmp_path / "previews")]) == 0

    summary = json.loads(capsys.readouterr().out)
    preview = json.loads((tmp_path / "previews" / "plan.master-sheet-write.json").read_text())
    assert summary["mode"] == "dry-run"
    assert not summary["blocked"]
    assert preview["column_values"]["stage"] == {"label": "In intake"}
