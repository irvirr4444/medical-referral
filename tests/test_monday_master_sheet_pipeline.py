from __future__ import annotations

import json
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace

from intake_extractor.monday_pdf_schema import MondayAgencyInformation, MondayPdfIntakeContract


_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
_MONDAY_DIR = _SRC / "monday.com"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
if str(_MONDAY_DIR) not in sys.path:
    sys.path.insert(0, str(_MONDAY_DIR))

_MODULE_PATH = _MONDAY_DIR / "inbound_intake_pipeline.py"
_SPEC = spec_from_file_location("inbound_intake_pipeline", _MODULE_PATH)
assert _SPEC and _SPEC.loader
inbound_pipeline = module_from_spec(_SPEC)
_SPEC.loader.exec_module(inbound_pipeline)


def test_inbound_pipeline_defaults_to_focused_monday_extractor(tmp_path, monkeypatch) -> None:
    pdf = tmp_path / "referral.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    config = tmp_path / "master-sheet-config.json"
    config.write_text(
        json.dumps(
            {
                "board_id": 5815942462,
                "group_id": "topics",
                "stage_label": "In intake",
                "phone_country_code": "US",
                "columns": {
                    "patient_dob": "date12",
                    "patient_phone": "phone",
                    "patient_email": "email2",
                    "stage": "deal_stage",
                    "comments": "text00__1",
                },
            }
        ),
        encoding="utf-8",
    )
    contract = MondayPdfIntakeContract(
        patient_name="Jane Doe",
        patient_date_of_birth="1950-01-02",
        patient_phone="555-555-0100",
        patient_email="jane@example.com",
        patient_address="1 Main St",
        referring_agency=MondayAgencyInformation(name="Example Home Health"),
        sent_by="Intake User",
    )
    calls: list[tuple[Path, str | None]] = []

    def fake_extract(path: Path, *, sent_by: str | None = None):
        calls.append((path, sent_by))
        return contract

    monkeypatch.setattr(inbound_pipeline, "extract_monday_from_pdf", fake_extract)
    attachment = SimpleNamespace(
        source="email",
        message_id="message-1",
        attachment_id="attachment-1",
        sha256="abc123",
        received_at="2026-08-03T12:00:00Z",
        subject="Referral",
        filename=pdf.name,
    )

    manifest = inbound_pipeline.process_inbound_pdf(
        attachment,
        pdf_path=pdf,
        output_dir=tmp_path / "output",
        write_config_path=config,
        sent_by="Intake User",
    )

    assert calls == [(pdf, "Intake User")]
    assert manifest["monday_contract_path"] == str(tmp_path / "output" / "monday-intake.json")
    preview = json.loads((tmp_path / "output" / "master-sheet-preview.json").read_text(encoding="utf-8"))
    assert preview["column_values"]["email2"] == {
        "email": "jane@example.com",
        "text": "jane@example.com",
    }
