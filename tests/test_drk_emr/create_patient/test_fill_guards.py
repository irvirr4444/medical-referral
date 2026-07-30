from __future__ import annotations

import pytest

from drk_emr.create_patient.fill import (
    FORBIDDEN_CREATE_PATIENT_IDS,
    FORBIDDEN_CREATE_PATIENT_TEXT,
    _is_forbidden_create_patient,
    safe_click,
)
from drk_emr.create_patient.synthetic_data import build_test_intake_data


class _FakeEl:
    def __init__(
        self,
        *,
        eid: str = "",
        text: str = "",
        aria: str = "",
        title: str = "",
        tag_name: str = "button",
        href: str = "",
    ) -> None:
        self._attrs = {"id": eid, "aria-label": aria, "title": title, "href": href, "value": ""}
        self.text = text
        self.tag_name = tag_name
        self.clicked = False

    def get_attribute(self, name: str) -> str:
        return self._attrs.get(name, "")

    def click(self) -> None:
        self.clicked = True


def test_synthetic_data_marks_test_values() -> None:
    data = build_test_intake_data()
    payload = data.to_dict()
    assert data.first_name == "TEST"
    assert "TEST" in data.primary_address1
    assert data.policy_number.startswith("TEST")
    assert "test" in data.email.lower()
    for key, value in payload.items():
        if not isinstance(value, str):
            continue
        if key in {
            "date_of_birth",
            "admission_date",
            "referral_date",
            "effective_date",
            "termination_date",
            "ssn",
            "primary_phone",
            "secondary_phone",
            "fax",
            "emergency_phone",
            "primary_state",
            "secondary_state",
            "care_state",
            "primary_zip",
            "secondary_zip",
            "care_zip",
            "gender_text",
            "language_text",
            "relationship_text",
            "insurance_type",
            "primary_country_text",
            "secondary_country_text",
            "copay",
            "deductible_amount",
            "percent_coverage",
            "deductible_met",
            "place_of_service_query",
            "facility_query",
            "home_health_query",
            "provider_query",
            "territory_query",
            "referral_source_query",
            "insurance_payer_query",
            "subscriber_relationship_text",
            "subscriber_date_of_birth",
        }:
            continue
        assert "test" in value.lower(), f"{key}={value!r} missing TEST marker"


def test_forbidden_create_patient_ids_include_bottom_button() -> None:
    assert "createPatientBtnBottom" in FORBIDDEN_CREATE_PATIENT_IDS
    assert FORBIDDEN_CREATE_PATIENT_TEXT == "create patient"


def test_safe_click_blocks_create_patient_button() -> None:
    el = _FakeEl(eid="createPatientBtnBottom", text="Create Patient")
    with pytest.raises(RuntimeError, match="Refusing to click Create Patient"):
        safe_click(el, purpose="should never run")
    assert el.clicked is False


def test_safe_click_allows_intake_nav_link_named_create_patient() -> None:
    el = _FakeEl(
        eid="",
        text="Create Patient",
        tag_name="a",
        href="https://drkemr.com/PatientIntake/Index",
    )
    safe_click(el, purpose="open intake form page")
    assert el.clicked is True


def test_safe_click_blocks_create_patient_by_text_alone() -> None:
    el = _FakeEl(eid="somethingElse", text="  Create Patient  ", tag_name="button")
    assert _is_forbidden_create_patient(el) is True
    with pytest.raises(RuntimeError):
        safe_click(el, purpose="blocked")


def test_safe_click_allows_add_insurance() -> None:
    el = _FakeEl(eid="saveInsuranceBtn", text="Add Insurance")
    safe_click(el, purpose="save insurance entry only")
    assert el.clicked is True
