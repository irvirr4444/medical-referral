from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ReferralBoardColumns:
    patient_name: str | None = None
    patient_dob: str | None = None
    patient_phone: str | None = None
    referring_facility: str | None = None
    referral_date: str | None = None
    insurance_provider: str | None = None
    requested_services: str | None = None
    extraction_status: str | None = None
    review_status: str | None = None
    notes: str | None = None
    source_pdf_file: str | None = None


@dataclass(frozen=True)
class ReferralBoardStatusDefaults:
    extraction_status: str | None = "Extracted"
    review_status: str | None = "Not Reviewed"


@dataclass(frozen=True)
class ReferralBoardConfig:
    board_id: int
    group_id: str
    item_name_mode: str = "patient_name"
    insurance_provider_mode: str = "dropdown"
    columns: ReferralBoardColumns = ReferralBoardColumns()
    status_defaults: ReferralBoardStatusDefaults = ReferralBoardStatusDefaults()


def load_referral_board_config(path: str | Path) -> ReferralBoardConfig:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return ReferralBoardConfig(
        board_id=int(payload["board_id"]),
        group_id=str(payload["group_id"]),
        item_name_mode=str(payload.get("item_name_mode") or "patient_name"),
        insurance_provider_mode=str(payload.get("insurance_provider_mode") or "dropdown"),
        columns=ReferralBoardColumns(**(payload.get("columns") or {})),
        status_defaults=ReferralBoardStatusDefaults(**(payload.get("status_defaults") or {})),
    )
