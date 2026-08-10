from __future__ import annotations

import json

from referral_pipeline import cli as intake


def test_monitor_command_processes_snapshot_into_database_and_report(tmp_path, capsys) -> None:
    snapshot_path = tmp_path / "monday.json"
    database_path = tmp_path / "workflow.sqlite"
    report_path = tmp_path / "report.json"
    snapshot_path.write_text(
        json.dumps(
            {
                "board": {"id": "5815942462", "name": "Master Sheet"},
                "items": [
                    {
                        "id": "item-1",
                        "name": "Synthetic Patient",
                        "updated_at": "2026-08-05T20:00:00Z",
                        "group": {"id": "working", "title": "Working pipeline"},
                        "column_values": [
                            {"id": "status7__1", "text": "Yes"},
                            {"id": "date_mm2gybh5", "text": "2026-08-05"},
                            {"id": "color_mkq3gga", "text": "Not Scheduled"},
                            {"id": "status0__1", "text": "No"},
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    exit_code = intake.main(
        [
            "monitor",
            "--monday-snapshot",
            str(snapshot_path),
            "--database-backend",
            "sqlite",
            "--sqlite-path",
            str(database_path),
            "--at",
            "2026-08-06T01:00:00Z",
            "--output",
            str(report_path),
        ]
    )

    assert exit_code == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["observed"] == 1
    assert report["scheduling"] == {"unscheduled": 1}
    assert report["exceptions_created"] == 1
    assert report["notifications"] == {"sent": 0, "mode": "outbox-only"}
    assert '"open_exceptions": 1' in capsys.readouterr().out


def test_health_command_reports_empty_store_without_failure(tmp_path, capsys) -> None:
    exit_code = intake.main(
        [
            "health",
            "--database-backend",
            "sqlite",
            "--sqlite-path",
            str(tmp_path / "workflow.sqlite"),
        ]
    )

    assert exit_code == 0
    assert '"overall_status": "no_data"' in capsys.readouterr().out
