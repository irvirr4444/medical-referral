"""Deterministic review-email rendering from canonical destination artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def render_review_email(
    *,
    review_id: str,
    token: str,
    canonical_path: str | Path,
    intake_plan_path: str | Path,
    monday_preview_path: str | Path,
    drk_draft_path: str | Path,
    write_config_path: str | Path,
    approval_allowed: bool = True,
) -> tuple[str, str]:
    canonical = _load(canonical_path)
    plan = _load(intake_plan_path)
    monday = _load(monday_preview_path)
    drk = _load(drk_draft_path)
    titles = _column_titles(write_config_path)
    patient = canonical.get("patient") or {}
    source = canonical.get("source") or {}
    clinical = canonical.get("clinical") or {}

    subject = f"[WCW REFERRAL REVIEW] {review_id}"
    sections = [
        "WCW REFERRAL REVIEW",
        f"Review ID: {review_id}",
        f"Source file: {_show(source.get('file_name'))}",
        "",
        "GENERAL REFERRAL SUMMARY",
        *_general_rows(canonical),
        "",
        "QUALITY AND DUPLICATE REVIEW",
        f"Intake outcome: {_show(plan.get('outcome'))}",
        f"Review reasons: {_show_list(plan.get('review_reasons'))}",
        f"Monday duplicate status: {_show((plan.get('monday_duplicate_check') or {}).get('status'))}",
        f"Monday duplicate candidates: {_show_list((plan.get('monday_duplicate_check') or {}).get('candidates'))}",
        f"Warnings: {_show_list(canonical.get('warnings'))}",
        *_quality_rows(canonical.get("field_quality") or {}),
        f"Monday write blocked: {'Yes' if monday.get('blocked') else 'No'}",
        f"Monday blockers: {_show_list(monday.get('blockers'))}",
        "",
        "MONDAY.COM PROPOSED WRITE",
        f"Item name: {_show(monday.get('item_name'))}",
        *_monday_rows(monday.get("column_values") or {}, titles),
        f"Mapping notes: {_show_list(monday.get('mapping_notes'))}",
        f"Post-create updates: {_show_list(monday.get('post_create_actions'))}",
        "",
        "DRK PROPOSED PATIENT DATA",
        f"Ready for form fill: {'Yes' if drk.get('ready_for_fill') else 'No'}",
        f"DRK blockers: {_show_list(drk.get('blockers'))}",
        f"DRK unresolved fields: {_show_list(drk.get('unresolved_fields'))}",
        *_flatten_rows(drk.get("payload") or {}),
        "",
        *_action_rows(review_id=review_id, token=token, approval_allowed=approval_allowed),
    ]
    if clinical.get("summary"):
        sections.insert(sections.index("QUALITY AND DUPLICATE REVIEW") - 1, f"Clinical summary: {clinical['summary']}")
    return subject, "\n".join(str(line) for line in sections)


def _action_rows(*, review_id: str, token: str, approval_allowed: bool) -> list[str]:
    if not approval_allowed:
        return [
            "ACTION REQUIRED",
            "This referral is blocked and cannot be approved for an automated write.",
            "Review the listed blockers and send corrections through the current manual process.",
        ]
    return [
        "ACTION REQUIRED",
        "Review the values above. To approve this exact artifact, reply with this line only:",
        f"CONFIRMED {review_id} {token}",
        "",
        "A confirmation can write the approved Monday payload. DRK patient creation is not yet automatic;",
        "the approved DRK draft remains an audited handoff until the guarded DRK submit path exists.",
    ]


def _general_rows(canonical: dict[str, Any]) -> list[str]:
    patient = canonical.get("patient") or {}
    name = patient.get("name") or {}
    address = patient.get("address") or {}
    source = canonical.get("referral_source") or {}
    source_org = source.get("organization") or {}
    hh = (canonical.get("home_health_or_hospice") or {}).get("organization") or {}
    insurances = canonical.get("insurances") or []
    services = canonical.get("requested_services") or []
    clinical = canonical.get("clinical") or {}
    phones = patient.get("phones") or []
    return [
        f"Patient: {_show(name.get('full') or _join(name.get('first'), name.get('middle'), name.get('last')))}",
        f"DOB: {_show(patient.get('date_of_birth'))}",
        f"Phone: {_show_list([item.get('number') for item in phones if isinstance(item, dict)])}",
        f"Address: {_show(_join(address.get('line_1'), address.get('line_2'), address.get('city'), address.get('state'), address.get('postal_code')))}",
        f"Referring organization: {_show(source_org.get('name'))}",
        f"Home health/hospice: {_show(hh.get('name'))}",
        f"Referral date: {_show(source.get('referral_or_order_date'))}",
        f"Insurance: {_show_list([_join(item.get('payer_name'), item.get('policy_number'), item.get('group_number')) for item in insurances if isinstance(item, dict)])}",
        f"Requested services: {_show_list([_join(item.get('service'), item.get('frequency'), item.get('instructions')) for item in services if isinstance(item, dict)])}",
        f"Diagnoses: {_show_list([_join(item.get('code'), item.get('description')) for item in clinical.get('diagnoses') or [] if isinstance(item, dict)])}",
        f"Medications: {_show_list([_join(item.get('name'), item.get('strength'), item.get('directions')) for item in clinical.get('medications') or [] if isinstance(item, dict)])}",
        f"Allergies: {_show_list([_join(item.get('name'), item.get('reaction')) for item in clinical.get('allergies') or [] if isinstance(item, dict)])}",
        f"Clinical notes: {_show_list(clinical.get('notes'))}",
    ]


def _quality_rows(quality: dict[str, Any]) -> list[str]:
    rows = []
    for field, value in sorted(quality.items()):
        if isinstance(value, dict):
            rows.append(f"{field}: {value.get('status', 'unknown')} / {value.get('confidence', 'unknown')}")
    return rows or ["Field quality: Not available"]


def _monday_rows(values: dict[str, Any], titles: dict[str, str]) -> list[str]:
    if not values:
        return ["Columns: No direct column values are currently mapped"]
    return [f"{titles.get(column_id, column_id)}: {_compact(value)}" for column_id, value in values.items()]


def _flatten_rows(value: dict[str, Any], prefix: str = "") -> list[str]:
    rows: list[str] = []
    for key, child in value.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(child, dict):
            rows.extend(_flatten_rows(child, path))
        elif isinstance(child, list):
            if child and all(isinstance(item, dict) for item in child):
                for index, item in enumerate(child):
                    rows.extend(_flatten_rows(item, f"{path}[{index}]"))
            elif child:
                rows.append(f"{path}: {_show_list(child)}")
        elif child is not None and child != "":
            rows.append(f"{path}: {child}")
    return rows or ["DRK fields: No values available"]


def _column_titles(path: str | Path) -> dict[str, str]:
    config = _load(path)
    columns = config.get("columns") or {}
    titles = config.get("column_titles") or {}
    return {
        str(column_id): str(titles.get(semantic_name) or semantic_name.replace("_", " ").title())
        for semantic_name, column_id in columns.items()
        if column_id
    }


def _load(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def _join(*values: Any) -> str:
    return " | ".join(str(value) for value in values if value not in (None, ""))


def _show(value: Any) -> str:
    return str(value) if value not in (None, "") else "MISSING"


def _show_list(values: Any) -> str:
    if not values:
        return "None"
    if isinstance(values, list):
        return "; ".join(_compact(value) for value in values if value not in (None, "")) or "None"
    return _compact(values)


def _compact(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)
