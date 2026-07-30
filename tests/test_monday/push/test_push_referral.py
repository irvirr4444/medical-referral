from __future__ import annotations

import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from intake_extractor.schema import ReferralIntake, RequestedService


_ROOT = Path(__file__).resolve()
while _ROOT != _ROOT.parent and not (_ROOT / "pyproject.toml").exists():
    _ROOT = _ROOT.parent
_SRC = _ROOT / "src"
_MONDAY_DIR = _SRC / "monday.com"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
if str(_MONDAY_DIR) not in sys.path:
    sys.path.insert(0, str(_MONDAY_DIR))

from referral_board_config import ReferralBoardColumns, ReferralBoardConfig

_MODULE_PATH = _MONDAY_DIR / "push_referral.py"
_SPEC = spec_from_file_location("push_referral", _MODULE_PATH)
assert _SPEC and _SPEC.loader
push_referral = module_from_spec(_SPEC)
_SPEC.loader.exec_module(push_referral)


def test_format_requested_services_renders_readable_lines() -> None:
    referral = ReferralIntake(
        requested_services=[
            RequestedService(service="Wound Care", frequency="3x/week", instructions="Eval and treat"),
            RequestedService(service="Physical Therapy"),
        ]
    )

    rendered = push_referral.format_requested_services(referral)

    assert rendered == (
        "Wound Care | freq: 3x/week | instr: Eval and treat\n"
        "Physical Therapy"
    )


def test_to_iso_date_handles_mmddyyyy() -> None:
    assert push_referral._to_iso_date("07/20/2026") == "2026-07-20"
    assert push_referral._to_iso_date("2026-07-20") is None


def test_build_item_name_prefers_patient_and_referral_date() -> None:
    referral = ReferralIntake(patient_name="Jane Doe", referral_date="07/20/2026", source_file="demo.pdf")

    item_name = push_referral.build_item_name(referral, Path("demo.pdf"), mode="patient_name")

    assert item_name == "Jane Doe - 07/20/2026"


def test_emit_uses_progress_callback() -> None:
    messages: list[str] = []

    push_referral._emit(messages.append, "hello progress")

    assert messages == ["hello progress"]


def test_build_column_values_supports_text_insurance_mode() -> None:
    referral = ReferralIntake(
        patient_name="Jane Doe",
        insurance_provider="Medi-Cal Molina",
    )
    config = ReferralBoardConfig(
        board_id=1,
        group_id="topics",
        insurance_provider_mode="text",
        columns=ReferralBoardColumns(
            patient_name="text_name",
            insurance_provider="text_insurance",
        ),
    )

    values = push_referral.build_column_values(referral, config)

    assert values["text_name"] == "Jane Doe"
    assert values["text_insurance"] == "Medi-Cal Molina"


def test_phone_for_monday_skips_placeholder_all_same_digits() -> None:
    assert push_referral._phone_for_monday("(999) 999-9999") is None
    assert push_referral._phone_for_monday("(773) 500-6400") == "(773) 500-6400"


def test_find_existing_item_prefers_attached_pdf_match() -> None:
    config = ReferralBoardConfig(
        board_id=1,
        group_id="topics",
        columns=ReferralBoardColumns(source_pdf_file="file_col"),
    )
    items = [
        {
            "id": "123",
            "name": "Some Other Name",
            "column_values": [
                {
                    "id": "file_col",
                    "value": '{"files":[{"name":"demo.pdf","assetId":1,"fileType":"ASSET"}]}',
                }
            ],
        }
    ]

    item, reason = push_referral.find_existing_item(
        items,
        config=config,
        pdf_filename="demo.pdf",
        item_name="Jane Doe - 07/20/2026",
    )

    assert item is not None
    assert item["id"] == "123"
    assert reason == "file"


def test_find_existing_item_falls_back_to_exact_name() -> None:
    config = ReferralBoardConfig(board_id=1, group_id="topics")
    items = [
        {"id": "123", "name": "Jane Doe - 07/20/2026", "column_values": []},
        {"id": "456", "name": "Other", "column_values": []},
    ]

    item, reason = push_referral.find_existing_item(
        items,
        config=config,
        pdf_filename="missing.pdf",
        item_name="Jane Doe - 07/20/2026",
    )

    assert item is not None
    assert item["id"] == "123"
    assert reason == "name"
