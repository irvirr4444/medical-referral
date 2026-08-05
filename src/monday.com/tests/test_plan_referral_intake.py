from __future__ import annotations

import json

from plan_referral_intake import main


def test_cli_writes_snapshot_plan_without_using_live_monday(tmp_path, capsys) -> None:
    referral_path = tmp_path / "referral.json"
    referral_path.write_text(
        json.dumps(
            {
                "patient_name": "Example, Patient",
                "patient_dob": "01/02/1980",
                "patient_phone": "555-555-0100",
                "patient_address": "1 Example Street",
                "referring_facility": "Example Home Health",
                "diagnosis_text": "Chronic wound",
                "insurance_provider": "Example Insurance",
            }
        )
    )
    records_path = tmp_path / "records.json"
    records_path.write_text(
        json.dumps(
            {
                "board": {"id": "1"},
                "items": [
                    {
                        "id": "123",
                        "name": "Patient, Example",
                        "group": {"title": "Working pipeline"},
                        "column_values": [
                            {"id": "date12", "text": "01/02/1980"},
                            {"id": "phone", "text": "555-555-0100"},
                            {"id": "location", "text": "1 Example Street"},
                        ],
                    }
                ],
            }
        )
    )

    assert (
        main(
            [
                "--referral-json",
                str(referral_path),
                "--monday-mode",
                "snapshot",
                "--monday-records-file",
                str(records_path),
                "--output-dir",
                str(tmp_path / "plans"),
            ]
        )
        == 0
    )
    output = json.loads(capsys.readouterr().out)
    plan = json.loads((tmp_path / "plans" / "referral.intake-plan.json").read_text())

    assert output["duplicate_candidate_count"] == 1
    assert plan["monday_duplicate_check"]["status"] == "duplicate_found"
    assert plan["write_safety"]["monday_writes_enabled"] is False
