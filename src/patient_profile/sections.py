"""Map captured DRK dashboard cards into profile extract sections."""

from __future__ import annotations

from typing import Any


def latest_encounter(cards: dict[str, Any]) -> dict[str, Any]:
    rows = _list_from_card(cards.get("encounters"), "encounters", "data")
    return rows[0] if rows else {}


def drk_sections_from_cards(cards: dict[str, Any]) -> list[dict[str, Any]]:
    demographics = _first_object(cards.get("patient_information"))
    admission = _first_object(cards.get("admission"))
    pipeline = _first_object(cards.get("pipeline"))
    referral = admission.get("referral") if isinstance(admission.get("referral"), dict) else {}
    encounters = _list_from_card(cards.get("encounters"), "encounters", "data")
    diagnoses = _diagnoses(cards.get("diagnosis"))
    medications = _items_from_marker(cards.get("medications_allergies"), "GetDoseSpotMedications")
    allergies_payload = _payload_from_marker(cards.get("medications_allergies"), "GetDoseSpotAllergies")
    allergies = _as_dicts(allergies_payload.get("items"))
    insurances = _insurances(cards.get("insurance"))
    notes = _communications(cards.get("communications"))
    scans = _list_from_card(cards.get("custom_scans"), "scans", "data")
    billing = _billing(cards.get("billing"))
    history = _as_dicts(admission.get("admissionHistory"))
    therapies = _as_dicts(pipeline.get("activeTherapies"))
    alerts = _as_dicts(pipeline.get("alerts"))
    tracks = _as_dicts(pipeline.get("therapyTrackStatuses"))
    timeline = _as_dicts(pipeline.get("timelineSteps"))
    auth = pipeline.get("priorAuthSummary") if isinstance(pipeline.get("priorAuthSummary"), dict) else {}
    quick_notes = _quick_notes(cards.get("quick_notes"))

    sections = [
        _fields_section(
            "demographics",
            "Demographics",
            [
                ("Name", demographics.get("fullName")),
                ("MRN", demographics.get("mrn")),
                ("Date of birth", demographics.get("dateOfBirth")),
                ("Age", demographics.get("age")),
                ("Gender", demographics.get("gender")),
                ("Status", demographics.get("patientStatusDisplayName") or demographics.get("status")),
                ("Status change", demographics.get("statusChangeDate")),
                ("Status reason", demographics.get("statusChangeReason")),
                ("Phone", demographics.get("phoneNumber")),
                ("Email", demographics.get("email")),
                ("Address", demographics.get("fullAddress")),
                ("City", demographics.get("city")),
                ("State", demographics.get("state")),
                ("ZIP", demographics.get("zipCode")),
                ("Emergency contact", demographics.get("emergencyContactName")),
                ("Emergency phone", demographics.get("emergencyContactPhone")),
            ],
            expanded=True,
        ),
        _fields_section(
            "admission",
            "Admission",
            [
                ("Admission date", admission.get("currentAdmissionDate") or referral.get("admissionDate")),
                ("Currently admitted", admission.get("isCurrentlyAdmitted")),
                ("Facility", admission.get("currentFacilityName") or demographics.get("facilityName")),
                ("Facility phone", admission.get("currentFacilityPhone")),
                ("Facility fax", admission.get("currentFacilityFax")),
                ("Place of service", demographics.get("placeOfServiceDescription") or admission.get("placeOfServiceCode")),
                ("Medicare admission", admission.get("currentMedicareAdmission")),
                ("Hospice", admission.get("isHospice")),
                ("Home health", demographics.get("homeHealthCompanyName") or admission.get("homeHealthCompany")),
                ("Patient status", admission.get("patientStatusDisplayName") or demographics.get("patientStatusDisplayName")),
                ("Status change", admission.get("statusChangeDate")),
                ("Status reason", admission.get("statusChangeReason")),
            ],
            expanded=True,
        ),
        _repeatable_section(
            "admission_history",
            "Admission history",
            history,
            [
                ("Status", "status"),
                ("Event", "eventType"),
                ("From", "fromStatusDisplayName"),
                ("To", "toStatusDisplayName"),
                ("Facility", "facilityName"),
                ("Provider", "providerName"),
                ("Admission date", "admissionDate"),
                ("Discharge date", "dischargeDate"),
                ("Discharge status", "dischargeStatusName"),
                ("Created by", "createdByUserName"),
                ("Created", "createdDate"),
            ],
            include_empty=False,
        ),
        _fields_section(
            "clinical",
            "Clinical",
            [
                ("Place of service", demographics.get("placeOfServiceDescription")),
                ("Home health", demographics.get("homeHealthCompanyName")),
                ("Hospice", admission.get("isHospice")),
                ("Last visit", demographics.get("lastVisit")),
                ("Marketer", referral.get("marketerName")),
                ("Referral date", referral.get("referralDate")),
                ("Referral notes", referral.get("notes")),
                ("Insurance type", referral.get("insuranceType")),
                ("Encounter summary", referral.get("encounterSummary")),
                ("Total encounters", referral.get("totalEncounters")),
                ("Initial encounters", referral.get("initialEncounters")),
                ("Progress encounters", referral.get("progressEncounters")),
            ],
        ),
        _fields_section(
            "pipeline",
            "Pipeline",
            [
                ("Stage", pipeline.get("currentStageName")),
                ("Previous stage", pipeline.get("previousStageName")),
                ("Days in stage", pipeline.get("daysInCurrentStage")),
                ("ACT status", pipeline.get("actStatusName")),
                ("Intake date", pipeline.get("intakeDate")),
                ("Intake status", pipeline.get("intakeStatusName")),
                ("QA hold reason", pipeline.get("qaHoldReason")),
                ("QA hold date", pipeline.get("qaHoldDate")),
                ("Territory", pipeline.get("territoryName")),
                ("Assigned ACT", pipeline.get("assignedActUserName")),
                ("Assigned QA", pipeline.get("assignedQaUserName")),
                ("Assigned billing", pipeline.get("assignedBillingUserName")),
                ("Assigned supplies", pipeline.get("assignedSuppliesUserName")),
                ("Prior auth", auth.get("statusName") or auth.get("status")),
                ("Auth number", auth.get("authNumber")),
            ],
            expanded=True,
        ),
        _repeatable_section(
            "therapies",
            "Therapies",
            therapies,
            [
                ("Type", "therapyType"),
                ("Status", "status"),
                ("Start date", "startDate"),
            ],
            expanded=True,
            include_empty=False,
        ),
        _repeatable_section(
            "pipeline_alerts",
            "Pipeline alerts",
            alerts,
            [
                ("Message", "message"),
                ("Severity", "severity"),
                ("Type", "alertType"),
                ("Action", "actionLabel"),
            ],
            include_empty=False,
        ),
        _repeatable_section(
            "therapy_tracks",
            "Therapy tracks",
            tracks,
            [
                ("Therapy", ("therapyTypeName", "therapyType")),
                ("Stage", "currentStageName"),
                ("Auth", ("detailedAuthStatusName", "authStatus")),
                ("Auth type", "authTypeName"),
                ("Hold", ("holdReasonName", "holdReason")),
                ("Hold date", "holdDate"),
            ],
            include_empty=False,
        ),
        _repeatable_section(
            "pipeline_timeline",
            "Pipeline timeline",
            timeline,
            [
                ("Stage", "stageName"),
                ("Status", "status"),
                ("Entered", "enteredDate"),
                ("Completed", "completedDate"),
                ("By", "completedByUserName"),
                ("Days", "daysInStage"),
            ],
            include_empty=False,
        ),
        _repeatable_section(
            "diagnoses",
            "Diagnoses",
            diagnoses,
            [
                ("Code", "code"),
                ("Description", "description"),
                ("Added date", "added"),
                ("Primary", "is_primary"),
                ("Status", "status"),
            ],
            expanded=True,
        ),
        _repeatable_section(
            "medications",
            "Medications",
            medications,
            [
                ("Name", ("displayName", "name")),
                ("Strength", "strength"),
                ("Dose form", "doseForm"),
                ("Directions", "directions"),
                ("Status", ("medicationStatus", "status")),
                ("Pharmacy status", "status"),
                ("Prescribed date", "writtenDate"),
                ("Effective date", "effectiveDate"),
                ("Last fill", "lastFillDate"),
                ("Prescriber", "prescriber"),
                ("Days supply", "daysSupply"),
                ("Quantity", "quantity"),
                ("Refills", "refills"),
                ("Pharmacy notes", "pharmacyNotes"),
            ],
            expanded=True,
        ),
        _allergy_section(allergies_payload, allergies),
        _repeatable_section(
            "notes",
            "Clinical notes",
            notes,
            [
                ("Note", "notes"),
                ("Subject", "subject"),
                ("When", "timestamp"),
                ("By", "userName"),
                ("Type", "communicationType"),
                ("Method", "contactMethod"),
                ("Department", "department"),
                ("Status", "status"),
            ],
        ),
        _repeatable_section(
            "quick_notes",
            "Quick notes",
            quick_notes,
            [
                ("Note", ("note", "notes", "text", "body")),
                ("When", ("timestamp", "createdDate")),
                ("By", ("userName", "createdBy")),
            ],
            include_empty=False,
        ),
        _repeatable_section(
            "insurance",
            "Insurance policies",
            insurances,
            [
                ("Type", "type"),
                ("Payer", "payerName"),
                ("Policy number", "policyNumber"),
                ("Group number", "groupNumber"),
                ("Group name", "groupName"),
                ("Policy holder", "subscriberName"),
                ("Effective date", "effectiveDate"),
                ("Expiration date", "expirationDate"),
                ("Patient is policy holder", "isPatientPolicyHolder"),
                ("Subscriber first name", "subscriberFirstName"),
                ("Subscriber last name", "subscriberLastName"),
                ("Subscriber date of birth", "subscriberDateOfBirth"),
                ("Primary", "isPrimary"),
                ("Active", "isActive"),
                ("Status", "status"),
                ("Copay", "copay"),
                ("Deductible", "deductible"),
                ("Percent coverage", "percentCoverage"),
                ("Verified with", "verifiedWith"),
            ],
            expanded=True,
        ),
        _repeatable_section(
            "encounters",
            "Encounters",
            encounters,
            [
                ("Date", "encounterDate"),
                ("Provider", "providerName"),
                ("Status", "status"),
                ("Service", "serviceType"),
                ("Chief complaint", "chiefComplaint"),
                ("Location", "location"),
                ("Signed", "isSigned"),
                ("Created by", "createdByName"),
                ("Role", "createdByRole"),
            ],
            expanded=True,
        ),
        _repeatable_section(
            "documents",
            "Documents",
            scans,
            [
                ("File", "fileName"),
                ("Category", "category"),
                ("Uploaded", "uploadDate"),
                ("Uploaded by", "uploadedBy"),
                ("Description", "description"),
                ("Type", "fileType"),
                ("Size", "fileSizeFormatted"),
            ],
        ),
        _fields_section(
            "billing",
            "Billing",
            [
                ("Collections status", billing.get("collectionsStatus")),
                ("Outstanding", billing.get("totalOutstanding")),
                ("Hold reason", billing.get("holdReason")),
                ("Active plan", billing.get("activePlan")),
                ("Patient", billing.get("patientName")),
            ],
        ),
    ]
    return [section for section in sections if section["fields"] or section.get("repeatable")]


def _allergy_section(payload: dict[str, Any], allergies: list[dict[str, Any]]) -> dict[str, Any]:
    nka = payload.get("noKnownAllergy")
    if nka is None:
        nka = payload.get("hasNoKnownAllergies")
    fields = [
        {
            "label": "No known allergies",
            "value": _display(nka) or "—",
            "rowId": "allergies.nka",
            "fixed": True,
        }
    ]
    fields.extend(
        _row_fields(
            allergies,
            [
                ("Name", "name"),
                ("Reaction", "reaction"),
                ("Type", "type"),
                ("Status", "statusType"),
            ],
            "allergies",
        )
    )
    return {
        "id": "allergies",
        "title": "Allergies",
        "defaultExpanded": False,
        "repeatable": True,
        "fields": fields,
    }


def _fields_section(
    section_id: str,
    title: str,
    pairs: list[tuple[str, Any]],
    *,
    expanded: bool = False,
) -> dict[str, Any]:
    fields = [{"label": label, "value": _display(value) or "—"} for label, value in pairs]
    return {
        "id": section_id,
        "title": title,
        "defaultExpanded": expanded,
        "fields": fields,
    }


def _repeatable_section(
    section_id: str,
    title: str,
    rows: list[dict[str, Any]],
    columns: list[tuple[str, str | tuple[str, ...]]],
    *,
    expanded: bool = False,
    include_empty: bool = True,
) -> dict[str, Any]:
    fields = _row_fields(rows, columns, section_id)
    if not fields and not include_empty:
        return {
            "id": section_id,
            "title": title,
            "defaultExpanded": False,
            "fields": [],
        }
    return {
        "id": section_id,
        "title": title,
        "defaultExpanded": expanded and bool(fields),
        "repeatable": True,
        "fields": fields,
    }


_IDENTIFYING_LABELS = {
    "Name",
    "Code",
    "Payer",
    "File",
    "Note",
    "Date",
    "Type",
    "Description",
    "Message",
    "Stage",
    "Therapy",
}


def _row_fields(
    rows: list[dict[str, Any]],
    columns: list[tuple[str, str | tuple[str, ...]]],
    prefix: str,
) -> list[dict[str, str]]:
    fields: list[dict[str, str]] = []
    for index, row in enumerate(rows):
        row_id = f"{prefix}.{index}"
        for label, key in columns:
            keys = key if isinstance(key, tuple) else (key,)
            value = _display(_value(row, *keys)) or "—"
            if value == "—" and label not in _IDENTIFYING_LABELS:
                continue
            fields.append(
                {
                    "label": label,
                    "value": value,
                    "rowId": row_id,
                }
            )
    return fields


def _diagnoses(card: Any) -> list[dict[str, Any]]:
    payload = _first_payload(card)
    if isinstance(payload.get("diagnoses"), list):
        return _as_dicts(payload.get("diagnoses"))
    return _as_dicts(_unwrap(payload, "diagnoses", "items", "data"))


def _insurances(card: Any) -> list[dict[str, Any]]:
    record = _record_for_marker(card, "GetInsurances") or _first_record(card)
    payload = _business(record)
    return _as_dicts(_unwrap(payload, "data", "items", "insurances"))


def _communications(card: Any) -> list[dict[str, Any]]:
    payload = _first_object(card)
    rows = _as_dicts(payload.get("communications"))
    usable: list[dict[str, Any]] = []
    for row in rows:
        if _display(row.get("notes")) or _display(row.get("subject")):
            usable.append(row)
    return usable


def _billing(card: Any) -> dict[str, Any]:
    payload = _first_payload(card)
    result = payload.get("result")
    if isinstance(result, dict):
        return result
    return _first_object(card)


def _items_from_marker(card: Any, marker: str) -> list[dict[str, Any]]:
    payload = _payload_from_marker(card, marker)
    return _as_dicts(payload.get("items") or payload.get("data"))


def _payload_from_marker(card: Any, marker: str) -> dict[str, Any]:
    record = _record_for_marker(card, marker)
    payload = _business(record)
    data = payload.get("data")
    return data if isinstance(data, dict) else payload


def _first_object(card: Any) -> dict[str, Any]:
    payload = _first_payload(card)
    data = payload.get("data")
    return data if isinstance(data, dict) else payload


def _first_payload(card: Any) -> dict[str, Any]:
    return _business(_first_record(card))


def _first_record(card: Any) -> dict[str, Any] | None:
    if not isinstance(card, dict):
        return None
    records = card.get("records") or []
    return records[0] if records and isinstance(records[0], dict) else None


def _record_for_marker(card: Any, marker: str) -> dict[str, Any] | None:
    if not isinstance(card, dict):
        return None
    for record in card.get("records") or []:
        if not isinstance(record, dict):
            continue
        url = str(((record.get("endpoint") or {}).get("url") if isinstance(record.get("endpoint"), dict) else "") or "")
        if marker.casefold() in url.casefold():
            return record
    return None


def _list_from_card(card: Any, *keys: str) -> list[dict[str, Any]]:
    payload = _first_object(card)
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return _as_dicts(value)
    return _as_dicts(_unwrap(_first_payload(card), *keys))


def _unwrap(payload: Any, *keys: str) -> Any:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            nested = _unwrap(value, *keys)
            if nested:
                return nested
    data = payload.get("data")
    if isinstance(data, list):
        return data
    return []


def _as_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _business(record: dict[str, Any] | None) -> dict[str, Any]:
    if not record:
        return {}
    business = record.get("business_data")
    return business if isinstance(business, dict) else {}


def _quick_notes(card: Any) -> list[dict[str, Any]]:
    payload = _first_payload(card)
    return _as_dicts(_unwrap(payload, "data", "notes", "items", "quickNotes"))


def _value(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row and row.get(key) not in (None, ""):
            return row.get(key)
        camel = key[:1].lower() + key[1:] if key else key
        if camel in row and row.get(camel) not in (None, ""):
            return row.get(camel)
    return None


def _display(value: Any) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    text = str(value).strip()
    if "T" in text and len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text.split("T", 1)[0]
    return text
