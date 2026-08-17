"""Fill Patient Intake form only — never creates a patient."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from dotenv import load_dotenv
from selenium.common.exceptions import TimeoutException
from selenium.webdriver import ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import Select, WebDriverWait
from seleniumwire import webdriver

from drk_emr.create_patient.schema import DrkCreatePayloadDraft
from drk_emr.create_patient.synthetic_data import SyntheticIntakeData, build_test_intake_data


LOGIN_PATH = "/Login/LoginView"
DASHBOARD_PATH = "/Dashboard"
INTAKE_PATH = "/PatientIntake/Index"

# Hard block: these must never be clicked by this script.
FORBIDDEN_CREATE_PATIENT_IDS = frozenset(
    {
        "createPatientBtnBottom",
        "createPatientBtn",
        "createPatientBtnTop",
        "btnCreatePatient",
    }
)
FORBIDDEN_CREATE_PATIENT_TEXT = "create patient"


def _safe_log(message: str) -> None:
    print(message, file=sys.stderr)


def _require_env(key: str) -> str:
    value = os.getenv(key, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return value


def _emr_root(emr_url: str) -> str:
    parsed = urlsplit(emr_url)
    if not parsed.scheme or not parsed.netloc:
        raise RuntimeError("EMR_URL must be an absolute URL")
    return f"{parsed.scheme}://{parsed.netloc}"


def _is_forbidden_create_patient(element: Any) -> bool:
    eid = (element.get_attribute("id") or "").strip()
    if eid in FORBIDDEN_CREATE_PATIENT_IDS:
        return True
    # The side-nav link text is also "Create Patient" but only opens the form page.
    href = (element.get_attribute("href") or "").strip()
    tag = (getattr(element, "tag_name", None) or element.get_attribute("tagName") or "").lower()
    if tag == "a" and "/patientintake/index" in href.lower():
        return False
    # Block submit/create actions by visible wording on buttons only.
    if tag not in {"button", "input"}:
        return False
    text = (element.text or "").strip().lower()
    value = (element.get_attribute("value") or "").strip().lower()
    aria = (element.get_attribute("aria-label") or "").strip().lower()
    title = (element.get_attribute("title") or "").strip().lower()
    blob = " ".join([text, value, aria, title])
    return FORBIDDEN_CREATE_PATIENT_TEXT in blob


def safe_click(element: Any, *, purpose: str) -> None:
    """Click helper that refuses Create Patient under any circumstance."""
    if _is_forbidden_create_patient(element):
        raise RuntimeError(
            f"Refusing to click Create Patient (purpose={purpose!r}, "
            f"id={(element.get_attribute('id') or '')!r})."
        )
    element.click()


def assert_create_patient_untouched(driver: webdriver.Chrome) -> None:
    """Sanity check: Create Patient buttons exist but were never our click targets."""
    for eid in FORBIDDEN_CREATE_PATIENT_IDS:
        matches = driver.find_elements(By.ID, eid)
        for el in matches:
            # Presence is fine; clicking is forbidden. Document for the run summary.
            _safe_log(f"Create Patient control present and untouched: #{eid} text={el.text!r}")


def submit_create_patient(
    driver: webdriver.Chrome,
    *,
    duplicate_decision: Any,
    confirm_create_patient: bool = False,
) -> None:
    """Submit Create Patient only after a fresh clear duplicate decision and explicit confirmation.

    The default create/fill path never calls this. It exists so a future submit
    path cannot accidentally bypass the duplicate gate.
    """
    from drk_emr.create_patient.duplicate_check import require_clear_to_create
    from drk_emr.create_patient.schema import DrkDuplicateCheckDecision

    if not isinstance(duplicate_decision, DrkDuplicateCheckDecision):
        raise TypeError("submit_create_patient requires a DrkDuplicateCheckDecision")
    require_clear_to_create(duplicate_decision)
    if not confirm_create_patient:
        raise RuntimeError(
            "Refusing Create Patient submit without confirm_create_patient=True "
            f"(duplicate status={duplicate_decision.status})."
        )
    raise RuntimeError(
        "Create Patient submit is intentionally unimplemented; "
        "duplicate gate passed but automatic submission remains disabled."
    )


def _make_driver(profile_dir: Path) -> webdriver.Chrome:
    options = ChromeOptions()
    options.add_argument(f"--user-data-dir={profile_dir}")
    options.add_argument("--window-size=1400,1100")
    options.add_argument("--no-first-run")
    options.add_argument("--disable-sync")
    return webdriver.Chrome(options=options, seleniumwire_options={"request_storage": "memory"})


def _login(driver: webdriver.Chrome, login_url: str, username: str, password: str) -> None:
    wait = WebDriverWait(driver, 30)
    driver.get(login_url)
    user = wait.until(
        ec.presence_of_element_located(
            (
                By.XPATH,
                "//input[@placeholder='User Name' or @name='User Name' or @id='UserName' or @name='UserName']",
            )
        )
    )
    pwd = wait.until(ec.presence_of_element_located((By.XPATH, "//input[@type='password']")))
    user.clear()
    user.send_keys(username)
    pwd.clear()
    pwd.send_keys(password)
    login_btn = wait.until(ec.element_to_be_clickable((By.XPATH, "//button[normalize-space()='Login']")))
    safe_click(login_btn, purpose="login")
    wait.until(lambda d: DASHBOARD_PATH.lower() in d.current_url.lower())


def navigate_to_patient_intake(driver: webdriver.Chrome) -> None:
    """Dashboard -> Patients rail -> Create Patient link -> /PatientIntake/Index."""
    wait = WebDriverWait(driver, 25)
    wait.until(lambda d: DASHBOARD_PATH.lower() in d.current_url.lower())
    patients_btn = wait.until(
        ec.element_to_be_clickable((By.CSS_SELECTOR, "button[data-panel='patients'][data-tip='Patients']"))
    )
    safe_click(patients_btn, purpose="open patients panel")
    create_link = wait.until(
        ec.element_to_be_clickable((By.CSS_SELECTOR, "a.nav-link[href='/PatientIntake/Index']"))
    )
    # This link only navigates to the intake form; it does not submit/create.
    safe_click(create_link, purpose="open intake form page")
    wait.until(lambda d: INTAKE_PATH.lower() in d.current_url.lower())
    wait.until(ec.presence_of_element_located((By.ID, "patientIntakeForm")))
    _wait_for_lookup_options(driver)


def _wait_for_lookup_options(driver: webdriver.Chrome, timeout_seconds: float = 20.0) -> None:
    """Gender/language/relationship options are filled async via GetLookupData."""

    def _ready(d: webdriver.Chrome) -> bool:
        try:
            gender = Select(d.find_element(By.ID, "genderIdentityId"))
            language = Select(d.find_element(By.ID, "languageId"))
            relationship = Select(d.find_element(By.ID, "relationshipId"))
            return len(gender.options) > 1 and len(language.options) > 1 and len(relationship.options) > 1
        except Exception:
            return False

    WebDriverWait(driver, timeout_seconds).until(_ready)


def _set_input(driver: webdriver.Chrome, element_id: str, value: str) -> None:
    el = WebDriverWait(driver, 15).until(ec.presence_of_element_located((By.ID, element_id)))
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    input_type = (el.get_attribute("type") or "").lower()
    if input_type in {"date", "number"}:
        # Locale-sensitive date/number typing is unreliable; set value directly.
        driver.execute_script(
            """
            const el = arguments[0];
            const val = arguments[1];
            el.focus();
            el.value = val;
            el.dispatchEvent(new Event('input', {bubbles: true}));
            el.dispatchEvent(new Event('change', {bubbles: true}));
            """,
            el,
            value,
        )
        return
    el.clear()
    el.send_keys(value)


def _set_checkbox(driver: webdriver.Chrome, element_id: str, checked: bool) -> None:
    el = WebDriverWait(driver, 15).until(ec.presence_of_element_located((By.ID, element_id)))
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    if el.is_selected() != checked:
        safe_click(el, purpose=f"toggle checkbox {element_id}")


def _select_by_visible_text(driver: webdriver.Chrome, element_id: str, visible_text: str) -> None:
    el = WebDriverWait(driver, 15).until(ec.presence_of_element_located((By.ID, element_id)))
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    select = Select(el)
    target = visible_text.strip().lower()
    # Exact match only — "male" must not match "Female".
    for option in select.options:
        text = (option.text or "").strip()
        if text.lower() != target:
            continue
        value = option.get_attribute("value")
        if value is not None and value != "":
            select.select_by_value(value)
        else:
            driver.execute_script(
                "arguments[0].selected = true; arguments[0].dispatchEvent(new Event('change', {bubbles:true}));",
                option,
            )
        return
    raise RuntimeError(f"Could not select {visible_text!r} on #{element_id}")


def _select_by_value(driver: webdriver.Chrome, element_id: str, value: str) -> None:
    el = WebDriverWait(driver, 15).until(ec.presence_of_element_located((By.ID, element_id)))
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    Select(el).select_by_value(value)


TYPEAHEAD_ITEM_SELECTOR = "div.p-3.cursor-pointer"
TYPEAHEAD_HIDDEN_IDS = {
    "placeOfServiceSearch": "placeOfServiceCode",
    "facilitySearch": "facilityId",
    "homeHealthSearch": "homeHealthCompanyId",
    "providerSearch": "providerId",
    "territorySearch": "territoryId",
    "marketerSearch": "referralSourceId",
    "insurancePayerSearch": "insurancePayerId",
}


def _dismiss_typeahead_dropdowns(driver: webdriver.Chrome) -> None:
    try:
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    except Exception:
        pass
    time.sleep(0.2)


def _visible_typeahead_items(wrapper: Any) -> list[Any]:
    items: list[Any] = []
    for el in wrapper.find_elements(By.CSS_SELECTOR, TYPEAHEAD_ITEM_SELECTOR):
        try:
            if el.is_displayed() and (el.text or "").strip():
                items.append(el)
        except Exception:
            continue
    return items


def _try_typeahead(
    driver: webdriver.Chrome,
    search_input_id: str,
    query: str,
    *,
    timeout_seconds: float = 8.0,
) -> dict[str, Any]:
    """Type query, wait for DRK dropdown rows, click one, confirm hidden id is set."""
    hidden_id = TYPEAHEAD_HIDDEN_IDS.get(search_input_id)
    result: dict[str, Any] = {
        "input_id": search_input_id,
        "hidden_id": hidden_id,
        "query": query,
        "selected": False,
        "selected_text": None,
        "hidden_value": None,
        "note": "",
    }
    _dismiss_typeahead_dropdowns(driver)
    el = WebDriverWait(driver, 15).until(ec.presence_of_element_located((By.ID, search_input_id)))
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    wrapper = el.find_element(By.XPATH, './ancestor::div[contains(@class,"relative")][1]')
    el.click()
    el.send_keys(Keys.COMMAND, "a")
    el.send_keys(Keys.BACKSPACE)
    time.sleep(0.15)
    el.send_keys(query)

    deadline = time.time() + timeout_seconds
    items: list[Any] = []
    while time.time() < deadline:
        items = _visible_typeahead_items(wrapper)
        if items:
            break
        time.sleep(0.25)

    if not items:
        # Fallback: global selector in case dropdown renders outside wrapper.
        items = [
            c
            for c in driver.find_elements(By.CSS_SELECTOR, TYPEAHEAD_ITEM_SELECTOR)
            if c.is_displayed() and (c.text or "").strip()
        ]
    if not items:
        result["note"] = f"no dropdown rows for query {query!r}"
        return result

    choice = items[0]
    text = (choice.text or "").strip()
    safe_click(choice, purpose=f"typeahead select for {search_input_id}")
    result["selected_text"] = text

    if hidden_id:
        def _hidden_ready(d: webdriver.Chrome) -> bool:
            val = d.find_element(By.ID, hidden_id).get_attribute("value") or ""
            return bool(val.strip())

        try:
            WebDriverWait(driver, 5).until(_hidden_ready)
            result["hidden_value"] = driver.find_element(By.ID, hidden_id).get_attribute("value")
        except TimeoutException:
            result["note"] = f"clicked {text!r} but hidden #{hidden_id} stayed empty"
            return result

    result["selected"] = True
    result["note"] = f"selected {text!r}"
    time.sleep(0.25)
    return result


def fill_intake_form(driver: webdriver.Chrome, data: SyntheticIntakeData) -> dict[str, Any]:
    """Fill all intake sections. Never clicks Create Patient."""
    notes: list[dict[str, Any]] = []
    wait = WebDriverWait(driver, 20)
    wait.until(ec.presence_of_element_located((By.ID, "patientIntakeForm")))

    # 1) Demographics
    _set_input(driver, "firstName", data.first_name)
    _set_input(driver, "middleName", data.middle_name)
    _set_input(driver, "lastName", data.last_name)
    _set_input(driver, "suffix", data.suffix)
    _set_input(driver, "ssn", data.ssn)
    _set_input(driver, "dateOfBirth", data.date_of_birth)
    _select_by_visible_text(driver, "genderIdentityId", data.gender_text)
    try:
        _select_by_visible_text(driver, "languageId", data.language_text)
    except Exception as exc:
        notes.append({"field": "languageId", "error": str(exc)})

    # 2) Address
    _set_input(driver, "primaryAddress1", data.primary_address1)
    _set_input(driver, "primaryAddress2", data.primary_address2)
    _set_input(driver, "primaryCity", data.primary_city)
    _select_by_value(driver, "primaryStateId", data.primary_state)
    _set_input(driver, "primaryZipCode", data.primary_zip)
    try:
        _select_by_visible_text(driver, "primaryCountryId", data.primary_country_text)
    except Exception as exc:
        notes.append({"field": "primaryCountryId", "error": str(exc)})

    _set_input(driver, "secondaryAddress1", data.secondary_address1)
    _set_input(driver, "secondaryAddress2", data.secondary_address2)
    _set_input(driver, "secondaryCity", data.secondary_city)
    _select_by_value(driver, "secondaryStateId", data.secondary_state)
    _set_input(driver, "secondaryZipCode", data.secondary_zip)
    try:
        _select_by_visible_text(driver, "secondaryCountryId", data.secondary_country_text)
    except Exception as exc:
        notes.append({"field": "secondaryCountryId", "error": str(exc)})

    # 3) Contact
    _set_input(driver, "primaryPhoneNumber", data.primary_phone)
    _set_input(driver, "secondaryPhoneNumber", data.secondary_phone)
    _set_input(driver, "email", data.email)
    _set_input(driver, "fax", data.fax)

    # 4) Emergency
    try:
        _select_by_visible_text(driver, "relationshipId", data.relationship_text)
    except Exception as exc:
        notes.append({"field": "relationshipId", "error": str(exc)})
    _set_input(driver, "relativeFirstName", data.relative_first_name)
    _set_input(driver, "relativeLastName", data.relative_last_name)
    _set_input(driver, "emergencyContactPhoneNumber", data.emergency_phone)
    _set_checkbox(driver, "patientGuardian", data.patient_guardian)
    _set_input(driver, "carePrimaryAddress1", data.care_address1)
    _set_input(driver, "carePrimaryAddress2", data.care_address2)
    _set_input(driver, "carePrimaryCity", data.care_city)
    _select_by_value(driver, "carePrimaryStateId", data.care_state)
    _set_input(driver, "carePrimaryZipCode", data.care_zip)

    # 5/6) Admission + referral
    _set_input(driver, "admissionDate", data.admission_date)
    notes.append(_try_typeahead(driver, "placeOfServiceSearch", data.place_of_service_query))
    notes.append(_try_typeahead(driver, "facilitySearch", data.facility_query))
    notes.append(_try_typeahead(driver, "homeHealthSearch", data.home_health_query))
    notes.append(_try_typeahead(driver, "providerSearch", data.provider_query))
    notes.append(_try_typeahead(driver, "territorySearch", data.territory_query))
    _set_checkbox(driver, "medicareAdmission", data.medicare_admission)
    _set_checkbox(driver, "palliativeAdmission", data.palliative_admission)
    _set_checkbox(driver, "hospice", data.hospice)
    notes.append(_try_typeahead(driver, "marketerSearch", data.referral_source_query))
    _set_input(driver, "referralDate", data.referral_date)

    # 7) Insurance — open form, fill, save insurance entry (NOT create patient)
    add_ins = wait.until(ec.element_to_be_clickable((By.ID, "addInsuranceBtn")))
    safe_click(add_ins, purpose="open insurance entry form")
    wait.until(ec.presence_of_element_located((By.ID, "insuranceEntryForm")))
    notes.append(_try_typeahead(driver, "insurancePayerSearch", data.insurance_payer_query))
    _select_by_value(driver, "insuranceType", data.insurance_type)
    _set_input(driver, "policyNumber", data.policy_number)
    _set_input(driver, "groupNumber", data.group_number)
    _set_input(driver, "groupName", data.group_name)
    _set_input(driver, "verifiedWith", data.verified_with)
    _set_input(driver, "effectiveDate", data.effective_date)
    _set_input(driver, "terminationDate", data.termination_date)
    _set_input(driver, "copay", data.copay)
    _set_input(driver, "deductibleAmount", data.deductible_amount)
    _set_input(driver, "percentCoverage", data.percent_coverage)
    _set_input(driver, "deductibleMet", data.deductible_met)
    _set_checkbox(driver, "isPatientPolicyHolder", data.is_patient_policy_holder)
    if not data.is_patient_policy_holder:
        # Toggle off reveals #subscriberSection (Policy Holder Information).
        section = wait.until(ec.visibility_of_element_located((By.ID, "subscriberSection")))
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", section)
        _set_input(driver, "subscriberFirstName", data.subscriber_first_name)
        _set_input(driver, "subscriberLastName", data.subscriber_last_name)
        _set_input(driver, "subscriberDateOfBirth", data.subscriber_date_of_birth)
        try:
            _select_by_visible_text(driver, "subscriberRelationshipId", data.subscriber_relationship_text)
        except Exception as exc:
            notes.append({"field": "subscriberRelationshipId", "error": str(exc)})
        notes.append({"subscriber_section": "filled", "is_patient_policy_holder": False})
    else:
        notes.append({"subscriber_section": "hidden", "is_patient_policy_holder": True})

    save_ins = wait.until(ec.element_to_be_clickable((By.ID, "saveInsuranceBtn")))
    # Extra guard: saveInsuranceBtn text is "Add Insurance", not Create Patient.
    if _is_forbidden_create_patient(save_ins):
        raise RuntimeError("saveInsuranceBtn unexpectedly matched Create Patient guard")
    safe_click(save_ins, purpose="save insurance entry only")
    time.sleep(1.0)

    assert_create_patient_untouched(driver)
    return {"filled": True, "created_patient": False, "notes": notes, "data": data.to_dict()}


def fill_intake_draft(driver: webdriver.Chrome, data: DrkCreatePayloadDraft) -> dict[str, Any]:
    """Fill only values explicitly present in a canonical DRK draft.

    This is intentionally separate from ``fill_intake_form``: that helper fills a
    complete synthetic fixture, while production referral drafts are sparse and
    must never inherit test defaults.
    """
    notes: list[dict[str, Any]] = []
    populated: list[str] = []
    wait = WebDriverWait(driver, 20)
    wait.until(ec.presence_of_element_located((By.ID, "patientIntakeForm")))

    def text(field_id: str, value: str | None) -> None:
        if value is None or not str(value).strip():
            return
        _set_input(driver, field_id, str(value).strip())
        populated.append(field_id)

    def select_text(field_id: str, value: str | None) -> None:
        if value is None or not str(value).strip():
            return
        _select_by_visible_text(driver, field_id, str(value).strip())
        populated.append(field_id)

    def select_value(field_id: str, value: str | None) -> None:
        if value is None or not str(value).strip():
            return
        _select_by_value(driver, field_id, str(value).strip())
        populated.append(field_id)

    def checkbox(field_id: str, value: bool | None) -> None:
        if value is None:
            return
        _set_checkbox(driver, field_id, value)
        populated.append(field_id)

    def typeahead(field_id: str, value: str | None) -> None:
        if value is None or not str(value).strip():
            return
        result = _try_typeahead(driver, field_id, str(value).strip())
        notes.append(result)
        if result.get("selected"):
            populated.append(field_id)

    demographics = data.demographics
    text("firstName", demographics.first_name)
    text("middleName", demographics.middle_name)
    text("lastName", demographics.last_name)
    text("suffix", demographics.suffix)
    text("ssn", demographics.ssn)
    text("dateOfBirth", demographics.date_of_birth)
    select_text("genderIdentityId", demographics.gender)
    select_text("languageId", demographics.preferred_language)

    for prefix, address in (
        ("primary", data.primary_address),
        ("secondary", data.secondary_address),
    ):
        text(f"{prefix}Address1", address.address_line_1)
        text(f"{prefix}Address2", address.address_line_2)
        text(f"{prefix}City", address.city)
        select_value(f"{prefix}StateId", address.state)
        text(f"{prefix}ZipCode", address.zip_code)
        select_text(f"{prefix}CountryId", address.country)

    contact = data.contact
    text("primaryPhoneNumber", contact.primary_phone)
    text("secondaryPhoneNumber", contact.secondary_phone)
    text("email", contact.email)
    text("fax", contact.fax)

    emergency = data.emergency_contact
    select_text("relationshipId", emergency.relationship)
    text("relativeFirstName", emergency.first_name)
    text("relativeLastName", emergency.last_name)
    text("emergencyContactPhoneNumber", emergency.phone)
    checkbox("patientGuardian", emergency.patient_guardian)
    text("carePrimaryAddress1", emergency.address_line_1)
    text("carePrimaryAddress2", emergency.address_line_2)
    text("carePrimaryCity", emergency.city)
    select_value("carePrimaryStateId", emergency.state)
    text("carePrimaryZipCode", emergency.zip_code)

    admission = data.admission
    text("admissionDate", admission.admission_date)
    typeahead("placeOfServiceSearch", admission.place_of_service_query)
    typeahead("facilitySearch", admission.facility_query)
    typeahead("homeHealthSearch", admission.home_health_query)
    typeahead("providerSearch", admission.provider_query)
    typeahead("territorySearch", admission.territory_query)
    checkbox("medicareAdmission", admission.medicare_admission)
    checkbox("palliativeAdmission", admission.palliative_care)
    checkbox("hospice", admission.hospice)

    referral = data.referral
    typeahead("marketerSearch", referral.referral_source_query)
    text("referralDate", referral.referral_date)
    for name, value in (
        ("clinical_referring_provider", referral.clinical_referring_provider),
        ("clinical_referring_facility", referral.clinical_referring_facility),
    ):
        if value:
            notes.append({"field": name, "value": value, "note": "not mapped to a verified DRK control"})

    for index, insurance in enumerate(data.insurances):
        values = insurance.model_dump(exclude_none=True)
        if not values:
            continue
        add_ins = wait.until(ec.element_to_be_clickable((By.ID, "addInsuranceBtn")))
        safe_click(add_ins, purpose="open insurance entry form")
        wait.until(ec.presence_of_element_located((By.ID, "insuranceEntryForm")))
        typeahead("insurancePayerSearch", insurance.payer_query)
        select_value("insuranceType", insurance.insurance_type)
        text("policyNumber", insurance.policy_number)
        text("groupNumber", insurance.group_number)
        text("groupName", insurance.group_name)
        text("verifiedWith", insurance.verified_with)
        text("effectiveDate", insurance.effective_date)
        text("terminationDate", insurance.termination_date)
        text("copay", insurance.copay)
        text("deductibleAmount", insurance.deductible_amount)
        text("percentCoverage", insurance.percent_coverage)
        text("deductibleMet", insurance.deductible_met)
        checkbox("isPatientPolicyHolder", insurance.is_patient_policy_holder)
        if insurance.is_patient_policy_holder is False and insurance.subscriber is not None:
            section = wait.until(ec.visibility_of_element_located((By.ID, "subscriberSection")))
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", section)
            text("subscriberFirstName", insurance.subscriber.first_name)
            text("subscriberLastName", insurance.subscriber.last_name)
            text("subscriberDateOfBirth", insurance.subscriber.date_of_birth)
            select_text("subscriberRelationshipId", insurance.subscriber.relationship_to_patient)
        save_ins = wait.until(ec.element_to_be_clickable((By.ID, "saveInsuranceBtn")))
        if _is_forbidden_create_patient(save_ins):
            raise RuntimeError("saveInsuranceBtn unexpectedly matched Create Patient guard")
        safe_click(save_ins, purpose="save insurance entry only")
        populated.append(f"insurance[{index}]")
        time.sleep(1.0)

    assert_create_patient_untouched(driver)
    return {
        "filled": bool(populated),
        "created_patient": False,
        "notes": notes,
        "populated_fields": populated,
    }


def read_filled_snapshot(driver: webdriver.Chrome) -> dict[str, Any]:
    """Read current visible values so the operator can verify fill-only succeeded."""
    ids = [
        "firstName",
        "middleName",
        "lastName",
        "suffix",
        "ssn",
        "dateOfBirth",
        "primaryAddress1",
        "primaryCity",
        "primaryZipCode",
        "primaryPhoneNumber",
        "email",
        "relativeFirstName",
        "relativeLastName",
        "admissionDate",
        "referralDate",
        "placeOfServiceSearch",
        "placeOfServiceCode",
        "facilitySearch",
        "facilityId",
        "homeHealthSearch",
        "homeHealthCompanyId",
        "providerSearch",
        "providerId",
        "territorySearch",
        "territoryId",
        "marketerSearch",
        "referralSourceId",
        "insurancePayerSearch",
        "insurancePayerId",
    ]
    values: dict[str, str] = {}
    for eid in ids:
        els = driver.find_elements(By.ID, eid)
        if els:
            values[eid] = els[0].get_attribute("value") or ""
    gender = driver.find_elements(By.ID, "genderIdentityId")
    if gender:
        values["genderIdentityId"] = Select(gender[0]).first_selected_option.text.strip()
    create_btns = []
    for eid in FORBIDDEN_CREATE_PATIENT_IDS:
        for el in driver.find_elements(By.ID, eid):
            create_btns.append({"id": eid, "text": el.text, "displayed": el.is_displayed()})
    return {
        "url": driver.current_url,
        "values": values,
        "create_patient_buttons_present": create_btns,
        "create_patient_clicked": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fill DRK Patient Intake with TEST data. NEVER clicks Create Patient."
    )
    parser.add_argument("--output-dir", default="output", help="Base output directory.")
    parser.add_argument(
        "--hold-seconds",
        type=int,
        default=90,
        help="Keep browser open after fill so you can inspect values (default 90).",
    )
    parser.add_argument(
        "--no-hold",
        action="store_true",
        help="Close browser immediately after fill (still never creates patient).",
    )
    parser.add_argument(
        "--skip-duplicate-check",
        action="store_true",
        help="Unsafe escape hatch for offline UI debugging only; never use for real intake.",
    )
    args = parser.parse_args(argv)

    load_dotenv()
    emr_url = _require_env("EMR_URL")
    username = _require_env("EMR_USERNAME")
    password = _require_env("EMR_PASSWORD")
    root = _emr_root(emr_url)
    login_url = f"{root}{LOGIN_PATH}"

    data = build_test_intake_data()
    output_dir = Path(args.output_dir).resolve() / "intake-fill-test"
    output_dir.mkdir(parents=True, exist_ok=True)
    profile_dir = output_dir / "_chrome_profile"
    if profile_dir.exists():
        shutil.rmtree(profile_dir, ignore_errors=True)
    profile_dir.mkdir(parents=True, exist_ok=True)

    from drk_emr.create_patient.adapters import synthetic_to_create_payload
    from drk_emr.create_patient.duplicate_check import (
        require_clear_to_create,
        run_duplicate_check,
        write_duplicate_check_audit,
    )

    driver: webdriver.Chrome | None = None
    summary: dict[str, Any] = {"created_patient": False}
    try:
        driver = _make_driver(profile_dir)
        _login(driver, login_url, username, password)
        _safe_log("Logged in; on Dashboard.")

        duplicate_decision = None
        if args.skip_duplicate_check:
            _safe_log("WARNING: skipping DRK duplicate gate (--skip-duplicate-check).")
        else:
            duplicate_decision = run_duplicate_check(driver, synthetic_to_create_payload(data))
            audit_path = write_duplicate_check_audit(
                output_dir / "drk-duplicate-check.json",
                duplicate_decision,
            )
            _safe_log(f"Duplicate gate written: {audit_path}")
            require_clear_to_create(duplicate_decision)

        navigate_to_patient_intake(driver)
        _safe_log("Opened Patient Intake form.")
        fill_result = fill_intake_form(driver, data)
        snapshot = read_filled_snapshot(driver)
        summary = {
            "created_patient": False,
            "duplicate_check": None
            if duplicate_decision is None
            else duplicate_decision.model_dump(mode="json"),
            "fill_result": fill_result,
            "snapshot": snapshot,
            "hold_seconds": 0 if args.no_hold else args.hold_seconds,
        }
        out_path = output_dir / "intake_fill_summary.json"
        out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8")
        _safe_log(f"Filled form with TEST data. Summary: {out_path}")
        _safe_log("CREATE PATIENT WAS NOT CLICKED.")

        hold = 0 if args.no_hold else max(0, args.hold_seconds)
        if hold:
            _safe_log(f"Holding browser open for {hold}s so you can inspect the filled form...")
            time.sleep(hold)
        return 0
    except Exception as exc:
        _safe_log(f"Intake fill aborted: {exc}")
        return 1
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass
        if profile_dir.exists():
            shutil.rmtree(profile_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
