"""Master Sheet write-target configuration.

Configuration parsing is independent of Monday network calls and mutations.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MasterSheetWriteConfig:
    board_id: int
    group_id: str
    stage_label: str
    phone_country_code: str
    patient_dob_column: str
    patient_phone_column: str
    stage_column: str
    referral_received_column: str | None = None
    patient_email_column: str | None = None
    agency_phone_column: str | None = None
    agency_contact_column: str | None = None
    agency_email_column: str | None = None
    place_of_service_column: str | None = None
    wound_order_included_column: str | None = None
    comments_column: str | None = None
    sent_by_column: str | None = None
    agency_relation_column: str | None = None
    current_hh_relation_column: str | None = None
    accounts_board_id: str | None = None
    case_manager_column: str | None = None
    sent_to_case_manager_column: str | None = None
    time_sent_to_case_manager_column: str | None = None
    default_case_manager_id: str | None = None
    sent_by_person_ids: dict[str, str] = field(default_factory=dict)
    write_stage: bool = False
    write_referral_received: bool = False


def load_master_sheet_write_config(path: str | Path) -> MasterSheetWriteConfig:
    """Load a target-specific mapping rather than relying on title-based writes."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    columns = payload.get("columns") or {}
    agency = payload.get("agency_relation") or {}
    routing = payload.get("routing") or {}
    sent_by_people = payload.get("sent_by_people") or {}
    writes = payload.get("writes") or {}
    return MasterSheetWriteConfig(
        board_id=int(payload["board_id"]),
        group_id=str(payload["group_id"]),
        stage_label=str(payload["stage_label"]),
        phone_country_code=str(payload["phone_country_code"]).upper(),
        patient_dob_column=str(columns["patient_dob"]),
        patient_phone_column=str(columns["patient_phone"]),
        stage_column=str(columns["stage"]),
        referral_received_column=_optional_string(columns.get("referral_received")),
        patient_email_column=_optional_string(columns.get("patient_email")),
        agency_phone_column=_optional_string(columns.get("agency_phone")),
        agency_contact_column=_optional_string(columns.get("agency_contact")),
        agency_email_column=_optional_string(columns.get("agency_email")),
        place_of_service_column=_optional_string(columns.get("place_of_service")),
        wound_order_included_column=_optional_string(columns.get("wound_order_included")),
        comments_column=_optional_string(columns.get("comments")),
        sent_by_column=_optional_string(columns.get("sent_by")),
        agency_relation_column=_optional_string(columns.get("agency_relation")),
        current_hh_relation_column=_optional_string(columns.get("current_hh_relation")),
        accounts_board_id=_optional_string(agency.get("accounts_board_id")),
        case_manager_column=_optional_string(columns.get("case_manager")),
        sent_to_case_manager_column=_optional_string(columns.get("sent_to_case_manager")),
        time_sent_to_case_manager_column=_optional_string(columns.get("time_sent_to_case_manager")),
        default_case_manager_id=_optional_string(routing.get("default_case_manager_id")),
        sent_by_person_ids={str(name).casefold(): str(person_id) for name, person_id in sent_by_people.items()},
        write_stage=bool(writes.get("stage", False)),
        write_referral_received=bool(writes.get("referral_received", False)),
    )


def _optional_string(value: Any) -> str | None:
    return str(value) if value is not None and str(value).strip() else None
