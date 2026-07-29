from __future__ import annotations

from drk_emr.redaction import mask_sensitive_headers, normalize_url_pattern, redact_json_payload


def test_mask_sensitive_headers_masks_cookie_and_tokens() -> None:
    headers = {
        "Cookie": "sessionid=abcdef123456",
        "Authorization": "Bearer abc",
        "X-Requested-With": "XMLHttpRequest",
        "__RequestVerificationToken": "tok12345",
    }
    out = mask_sensitive_headers(headers)
    assert out["Cookie"].startswith("[MASKED:")
    assert out["Authorization"].startswith("[MASKED:")
    assert out["__RequestVerificationToken"].startswith("[MASKED:")
    assert out["X-Requested-With"] == "XMLHttpRequest"


def test_normalize_url_pattern_replaces_patient_id_and_numeric_segments() -> None:
    url = "https://drkemr.com/PatientDashboard/Index/12345?patientId=987654&visitId=111222"
    out = normalize_url_pattern(url, patient_id="987654")
    assert "{patientId}" in out
    assert "{id}" in out


def test_normalize_url_pattern_redacts_credentials_in_query() -> None:
    url = "https://drkemr.com/Login/ValidateUser?userName=secretuser&password=secretpass&timeZoneId=UTC"
    out = normalize_url_pattern(url)
    assert "secretuser" not in out
    assert "secretpass" not in out
    assert "userName=[REDACTED]" in out
    assert "password=[REDACTED]" in out


def test_redact_json_payload_replaces_pii_fields() -> None:
    payload = {
        "patientName": "Jane Doe",
        "dob": "1990-01-01",
        "contact": {"email": "jane@example.com", "phone": "5551234567"},
        "nested": [{"mrn": "123456"}, {"value": "normal"}],
    }
    out = redact_json_payload(payload)
    assert out["patientName"] == "[REDACTED]"
    assert out["dob"] == "[REDACTED]"
    assert out["contact"]["email"] == "[REDACTED]"
    assert out["contact"]["phone"] == "[REDACTED]"
    assert out["nested"][0]["mrn"] == "[REDACTED]"
    assert out["nested"][1]["value"] == "normal"

