from __future__ import annotations

from patient_profile.lookup import (
    drk_profile_from_cards,
    identity_sync,
    lookup_patient,
    monday_record,
    short_source_error,
)


def _item(item_id: str, name: str, **fields: str) -> dict:
    columns = {
        "dob": "date12",
        "phone": "phone",
        "address": "location",
        "pos": "status_1__1",
        "case_manager": "deal_owner",
        "referral_sent": "status3__1",
        "provider": "mirror03__1",
        "appointment": "date9__1",
        "scheduled": "color_mkq3gga",
        "scheduled_complete": "status0__1",
        "visit": "status5__1",
        "sent_by": "people0",
        "agency_contact": "text6__1",
        "sent_to_cm": "status7__1",
    }
    values = []
    for key, column_id in columns.items():
        if key in fields:
            values.append({"id": column_id, "text": fields[key]})
    return {
        "id": item_id,
        "name": name,
        "group": {"title": "Working pipeline"},
        "column_values": values,
    }


def _drk_cards(*, patient_id: int = 77, **data: object) -> dict:
    payload = {
        "id": patient_id,
        "firstName": "Alva",
        "lastName": "Butler",
        "fullName": "Alva Butler",
        "dateOfBirth": "1940-10-04T00:00:00",
        "phoneNumber": "8135550100",
        "city": "Tampa",
        "mrn": "MRN-77",
        "patientStatusDisplayName": "Active",
        "facilityName": "Tampa General",
        **data,
    }
    return {
        "patient_information": {
            "card": "patient_information",
            "records": [{"business_data": {"data": payload}}],
        },
        "encounters": {"card": "encounters", "records": []},
        "pipeline": {"card": "pipeline", "records": []},
    }


def test_lookup_returns_monday_and_drk_for_first_last_slug() -> None:
    items = [
        _item(
            "m1",
            "BUTLER, ALVA",
            dob="10/04/1940",
            phone="(813) 555-0100",
            provider="Jane Provider",
            sent_by="Case Management",
            visit="Scheduled",
        )
    ]
    candidates = [
        {
            "patient_id": "77",
            "display_name": "Alva Butler",
            "first_name": "Alva",
            "last_name": "Butler",
            "date_of_birth": "1940-10-04T00:00:00",
        }
    ]
    profile = drk_profile_from_cards("77", _drk_cards(providerName="Other Provider"))
    profile["provider"] = "Other Provider"

    result = lookup_patient(
        "alva-butler",
        monday_fetch=lambda _name: items,
        drk_search=lambda _name: candidates,
        drk_read=lambda _patient_id: profile,
    )

    assert result.status == 200
    assert result.body["query"]["given_family"] == "Alva Butler"
    assert result.body["query"]["last_first"] == "BUTLER, ALVA"
    assert result.body["monday"]["item_id"] == "m1"
    assert result.body["monday"]["sent_by"] == "Case Management"
    assert result.body["drk"]["patient_id"] == "77"
    assert result.body["match"]["status"] == "mismatch"
    assert any(field["field"] == "provider" and field["status"] == "mismatch" for field in result.body["match"]["fields"])


def test_lookup_404_when_neither_source_has_the_name() -> None:
    result = lookup_patient(
        "alva-butler",
        monday_fetch=lambda _name: [],
        drk_search=lambda _name: [],
        drk_read=lambda _patient_id: {},
    )
    assert result.status == 404
    assert result.body["error"] == "not_found"


def test_lookup_409_when_monday_name_is_ambiguous() -> None:
    items = [
        _item("1", "BUTLER, ALVA", dob="10/04/1940"),
        _item("2", "Butler, Alva", dob="01/01/1950"),
    ]
    result = lookup_patient(
        "alva-butler",
        monday_fetch=lambda _name: items,
        drk_search=lambda _name: [],
        drk_read=lambda _patient_id: {},
    )
    assert result.status == 409
    assert result.body["error"] == "ambiguous"
    assert len(result.body["candidates"]["monday"]) == 2


def test_lookup_502_returns_monday_when_drk_fails() -> None:
    items = [_item("m1", "BUTLER, ALVA", dob="10/04/1940")]

    def boom(_name: str) -> list:
        raise RuntimeError("chrome down")

    result = lookup_patient(
        "alva-butler",
        monday_fetch=lambda _name: items,
        drk_search=boom,
        drk_read=lambda _patient_id: {},
    )
    assert result.status == 502
    assert result.body["monday"]["item_id"] == "m1"
    assert result.body["drk"] is None
    assert result.body["errors"][0]["source"] == "drk"
    assert result.body["errors"][0]["message"] == "chrome down"


def test_lookup_strips_selenium_chrome_crash_dump() -> None:
    items = [_item("m1", "BUTLER, ALVA", dob="10/04/1940")]
    dump = (
        "Message: session not created: Chrome instance exited. Examine ChromeDriver verbose log "
        "to determine the cause.; For documentation on this error, please visit: "
        "https://www.selenium.dev/documentation/webdriver/troubleshooting/errors/sessionnotcreated\n"
        "Stacktrace:\n"
        "0   chromedriver                        0x0000000102a0e2b8 xxx + 123"
    )

    def boom(_name: str) -> list:
        raise RuntimeError(dump)

    result = lookup_patient(
        "alva-butler",
        monday_fetch=lambda _name: items,
        drk_search=boom,
        drk_read=lambda _patient_id: {},
    )
    assert result.status == 502
    assert result.body["errors"][0]["message"] == "DRK chart is temporarily unavailable."
    assert "Stacktrace" not in result.body["errors"][0]["message"]


def test_short_source_error_keeps_first_line_of_generic_failures() -> None:
    exc = RuntimeError("Monday GraphQL timed out\nmore detail")
    assert short_source_error(exc, source="monday") == "Monday GraphQL timed out"


def test_short_source_error_hides_dead_selenium_session_dump() -> None:
    exc = RuntimeError(
        "Message: invalid session id; For documentation on this error, please visit:\n"
        "https://www.selenium.dev/documentation/webdriver/troubleshooting/errors"
    )
    assert short_source_error(exc, source="drk") == "DRK chart is temporarily unavailable."


def test_identity_sync_matches_normalized_dob_and_phone() -> None:
    monday = monday_record(_item("1", "BUTLER, ALVA", dob="10/04/1940", phone="813-555-0100", provider="Pat"))
    drk = {
        "dob": "1940-10-04T00:00:00",
        "phone": "(813) 555-0100",
        "provider": "Pat",
    }
    assert identity_sync(monday, drk)["status"] == "match"


def test_drk_profile_reads_demographics_card() -> None:
    profile = drk_profile_from_cards("77", _drk_cards())
    assert profile["name"] == "Alva Butler"
    assert profile["mrn"] == "MRN-77"
    assert "1940-10-04" in profile["dob"]
