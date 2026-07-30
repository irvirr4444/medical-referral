"""Conservative Master Sheet create path driven by an approved intake plan.

This module deliberately cannot update duplicate candidates. It maps only fields
whose Master Sheet destination and Monday value format are currently verified.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from intake_extractor.schema import ReferralIntake
from monday_api import monday_graphql


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
    agency_phone_column: str | None = None
    comments_column: str | None = None
    agency_relation_column: str | None = None
    accounts_board_id: str | None = None
    case_manager_column: str | None = None
    sent_to_case_manager_column: str | None = None
    time_sent_to_case_manager_column: str | None = None
    default_case_manager_id: str | None = None


def load_master_sheet_write_config(path: str | Path) -> MasterSheetWriteConfig:
    """Load a target-specific mapping rather than relying on title-based writes."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    columns = payload.get("columns") or {}
    agency = payload.get("agency_relation") or {}
    routing = payload.get("routing") or {}
    return MasterSheetWriteConfig(
        board_id=int(payload["board_id"]),
        group_id=str(payload["group_id"]),
        stage_label=str(payload["stage_label"]),
        phone_country_code=str(payload["phone_country_code"]).upper(),
        patient_dob_column=str(columns["patient_dob"]),
        patient_phone_column=str(columns["patient_phone"]),
        stage_column=str(columns["stage"]),
        referral_received_column=_optional_string(columns.get("referral_received")),
        agency_phone_column=_optional_string(columns.get("agency_phone")),
        comments_column=_optional_string(columns.get("comments")),
        agency_relation_column=_optional_string(columns.get("agency_relation")),
        accounts_board_id=_optional_string(agency.get("accounts_board_id")),
        case_manager_column=_optional_string(columns.get("case_manager")),
        sent_to_case_manager_column=_optional_string(columns.get("sent_to_case_manager")),
        time_sent_to_case_manager_column=_optional_string(columns.get("time_sent_to_case_manager")),
        default_case_manager_id=_optional_string(routing.get("default_case_manager_id")),
    )


def build_master_sheet_create_preview(
    plan: dict[str, Any],
    *,
    config: MasterSheetWriteConfig,
    agency_matches: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Build a create request or an explicit reason why it is blocked."""
    referral = ReferralIntake.model_validate(plan.get("referral") or {})
    duplicate = plan.get("monday_duplicate_check") or {}
    route_to_case_manager = _route_to_case_manager(plan)
    blockers = _create_blockers(plan, duplicate, route_to_case_manager=route_to_case_manager, config=config)
    columns, mapping_notes = _mapped_columns(
        referral,
        source=plan.get("source") or {},
        config=config,
        agency_matches=agency_matches or [],
        route_to_case_manager=route_to_case_manager,
    )
    post_create_actions = _post_create_actions(referral)
    preview: dict[str, Any] = {
        "board_id": config.board_id,
        "group_id": config.group_id,
        "operation": "create_item",
        "item_name": referral.patient_name,
        "column_values": columns,
        "mapping_notes": mapping_notes,
        "post_create_actions": post_create_actions,
        "blocked": bool(blockers),
        "blockers": blockers,
    }
    if not blockers and not preview["item_name"]:
        preview["blocked"] = True
        preview["blockers"].append("missing_patient_name")
    return preview


def create_master_sheet_item(preview: dict[str, Any]) -> dict[str, Any]:
    """Create one pre-validated item, then return Monday's item identity."""
    if preview.get("blocked"):
        raise ValueError("Blocked previews cannot be applied to the Master Sheet.")
    response = monday_graphql(
        """
        mutation ($boardId: ID!, $groupId: String!, $itemName: String!, $columnValues: JSON!) {
          create_item(
            board_id: $boardId,
            group_id: $groupId,
            item_name: $itemName,
            column_values: $columnValues
          ) { id name }
        }
        """,
        variables={
            "boardId": str(preview["board_id"]),
            "groupId": str(preview["group_id"]),
            "itemName": str(preview["item_name"]),
            "columnValues": json.dumps(preview["column_values"]),
        },
    )
    item = response.get("data", {}).get("create_item")
    if not isinstance(item, dict) or not item.get("id"):
        raise RuntimeError("Monday did not return a created item ID.")
    return item


def apply_master_sheet_create(preview: dict[str, Any]) -> dict[str, Any]:
    """Create a planned item and retain intake context in an item update."""
    item = create_master_sheet_item(preview)
    applied_actions: list[dict[str, Any]] = []
    for action in preview.get("post_create_actions") or []:
        if action.get("type") == "create_update":
            update = _create_item_update(item_id=str(item["id"]), body=str(action["body"]))
            applied_actions.append({"type": "create_update", "update_id": update["id"]})
    return {"item": item, "applied_actions": applied_actions}


def _create_blockers(
    plan: dict[str, Any],
    duplicate: dict[str, Any],
    *,
    route_to_case_manager: bool,
    config: MasterSheetWriteConfig,
) -> list[str]:
    blockers: list[str] = []
    review_reasons = set(plan.get("review_reasons") or [])
    allowed_partial_route = plan.get("outcome") == "manual_review_required" and review_reasons == {"missing_supporting_fields"}
    if plan.get("outcome") != "ready_for_human_approval" and not allowed_partial_route:
        blockers.append(f"plan_outcome_is_{plan.get('outcome') or 'unknown'}")
    duplicate_status = duplicate.get("status")
    if duplicate_status != "no_candidates_found":
        blockers.append(f"duplicate_check_is_{duplicate_status or 'missing'}")
    if route_to_case_manager and not config.default_case_manager_id:
        blockers.append("case_manager_not_configured_for_required_route")
    return blockers


def _mapped_columns(
    referral: ReferralIntake,
    *,
    source: dict[str, Any],
    config: MasterSheetWriteConfig,
    agency_matches: list[dict[str, str]],
    route_to_case_manager: bool,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    columns: dict[str, Any] = {config.stage_column: {"label": config.stage_label}}
    notes: list[dict[str, str]] = []

    dob = _iso_date(referral.patient_dob)
    if dob:
        columns[config.patient_dob_column] = {"date": dob}
    elif referral.patient_dob:
        notes.append({"field": "patient_dob", "reason": "not_written_unrecognized_date_format"})

    phone = _phone_value(referral.patient_phone, country=config.phone_country_code)
    if phone:
        columns[config.patient_phone_column] = phone
    elif referral.patient_phone:
        notes.append({"field": "patient_phone", "reason": "not_written_unrecognized_phone_format"})

    received_value = _source_received_value(source)
    if config.referral_received_column and received_value:
        columns[config.referral_received_column] = received_value
    elif config.referral_received_column:
        notes.append({"field": "referral_received", "reason": "not_written_missing_inbound_received_timestamp"})

    if config.agency_phone_column and referral.referring_phone:
        columns[config.agency_phone_column] = referral.referring_phone

    if referral.referring_facility:
        _map_agency_relation(columns, notes, config=config, matches=agency_matches)

    if route_to_case_manager and config.default_case_manager_id:
        if config.case_manager_column:
            columns[config.case_manager_column] = {
                "personsAndTeams": [{"id": int(config.default_case_manager_id), "kind": "person"}]
            }
        if config.sent_to_case_manager_column:
            columns[config.sent_to_case_manager_column] = {"label": "Yes"}
        if config.time_sent_to_case_manager_column:
            columns[config.time_sent_to_case_manager_column] = {"date": datetime.now().strftime("%Y-%m-%d")}

    if config.comments_column:
        summary = _format_intake_summary(referral)
        if summary:
            columns[config.comments_column] = summary

    # Monday's location field needs coordinates. Do not send PHI to a third-party
    # geocoder without approval; the raw address is instead retained in Comments.
    if referral.patient_address:
        notes.append({"field": "patient_address", "reason": "stored_in_comments_and_item_update_location_requires_approved_geocoding"})
    if referral.referral_date:
        notes.append({"field": "referral_date", "reason": "stored_in_comments_not_equivalent_to_referral_received_timestamp"})
    if referral.insurance_provider or referral.insurance_id:
        notes.append({"field": "insurance", "reason": "stored_in_comments_and_item_update_no_dedicated_master_sheet_column"})
    if referral.diagnosis_text or referral.icd10_codes or referral.requested_services:
        notes.append({"field": "clinical_information", "reason": "stored_in_comments_and_item_update_no_dedicated_master_sheet_column"})
    return columns, notes


def _map_agency_relation(
    columns: dict[str, Any],
    notes: list[dict[str, str]],
    *,
    config: MasterSheetWriteConfig,
    matches: list[dict[str, str]],
) -> None:
    if not config.agency_relation_column:
        notes.append({"field": "referring_facility", "reason": "preserved_in_item_update_agency_relation_not_configured"})
    elif len(matches) == 1 and matches[0].get("id"):
        columns[config.agency_relation_column] = {"item_ids": [matches[0]["id"]]}
    elif len(matches) > 1:
        notes.append({"field": "referring_facility", "reason": "preserved_in_item_update_multiple_agency_matches"})
    else:
        notes.append({"field": "referring_facility", "reason": "preserved_in_item_update_no_exact_agency_match"})


def _route_to_case_manager(plan: dict[str, Any]) -> bool:
    return any(action.get("type") == "route_partial_referral_to_case_manager" for action in plan.get("proposed_actions") or [])


def _post_create_actions(referral: ReferralIntake) -> list[dict[str, str]]:
    return [{"type": "create_update", "body": _format_intake_context(referral)}]


def _format_intake_context(referral: ReferralIntake) -> str:
    services = "; ".join(
        " | ".join(part for part in (service.service, service.frequency, service.instructions) if part)
        for service in referral.requested_services
    )
    rows = [
        "<p><strong>Automated intake context - pending human review</strong></p>",
        _html_row("Patient address", referral.patient_address),
        _html_row("Referring agency", referral.referring_facility),
        _html_row("Referral date", referral.referral_date),
        _html_row("Insurance", _join_values(referral.insurance_provider, referral.insurance_id, referral.insurance_group_number)),
        _html_row("Clinical information", _join_values(referral.diagnosis_text, ", ".join(referral.icd10_codes))),
        _html_row("Requested services", services or None),
        _html_row("Notes", referral.notes),
    ]
    return "".join(row for row in rows if row)


def _format_intake_summary(referral: ReferralIntake) -> str | None:
    """Keep unmodeled PDF facts visible in the populated Master Sheet comments field."""
    services = "; ".join(
        " | ".join(part for part in (service.service, service.frequency, service.instructions) if part)
        for service in referral.requested_services
    )
    values = (
        ("Patient address", referral.patient_address),
        ("Referring agency", referral.referring_facility),
        ("Referral date", referral.referral_date),
        ("Insurance", _join_values(referral.insurance_provider, referral.insurance_id, referral.insurance_group_number)),
        ("Clinical information", _join_values(referral.diagnosis_text, ", ".join(referral.icd10_codes))),
        ("Requested services", services or None),
        ("Notes", referral.notes),
    )
    summary = " | ".join(f"{label}: {value}" for label, value in values if value)
    return summary or None


def _html_row(label: str, value: str | None) -> str:
    if not value:
        return ""
    escaped = value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"<p><strong>{label}:</strong> {escaped}</p>"


def _join_values(*values: str | None) -> str | None:
    result = " | ".join(value for value in values if value)
    return result or None


def _create_item_update(*, item_id: str, body: str) -> dict[str, Any]:
    response = monday_graphql(
        """
        mutation ($itemId: ID!, $body: String!) {
          create_update(item_id: $itemId, body: $body) { id }
        }
        """,
        variables={"itemId": item_id, "body": body},
    )
    update = response.get("data", {}).get("create_update")
    if not isinstance(update, dict) or not update.get("id"):
        raise RuntimeError("Monday did not return an update ID.")
    return update


def _optional_string(value: Any) -> str | None:
    return str(value) if value is not None and str(value).strip() else None


def _iso_date(value: str | None) -> str | None:
    if not value:
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(value.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _source_received_value(source: dict[str, Any]) -> dict[str, str] | None:
    value = source.get("received_at")
    if not value:
        return None
    normalized = str(value).replace("Z", "+00:00")
    try:
        received = datetime.fromisoformat(normalized)
        if received.tzinfo is not None:
            received = received.astimezone(timezone.utc)
        result = {"date": received.strftime("%Y-%m-%d")}
        if "T" in normalized or " " in normalized:
            result["time"] = received.strftime("%H:%M:%S")
        return result
    except ValueError:
        date = _iso_date(str(value))
        return {"date": date} if date else None


def _phone_value(value: str | None, *, country: str) -> dict[str, str] | None:
    if not value:
        return None
    digits = "".join(character for character in value if character.isdigit())
    if country == "US" and len(digits) == 10:
        return {"phone": f"+1{digits}", "countryShortName": country}
    if country == "US" and len(digits) == 11 and digits.startswith("1"):
        return {"phone": f"+{digits}", "countryShortName": country}
    if value.startswith("+") and len(digits) >= 8:
        return {"phone": f"+{digits}", "countryShortName": country}
    return None
