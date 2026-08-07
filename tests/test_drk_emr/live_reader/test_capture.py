from __future__ import annotations

import json

from drk_emr.live_reader.capture import capture_dashboard_cards


class Response:
    def __init__(self, payload: object) -> None:
        self.body = json.dumps(payload).encode("utf-8")
        self.headers = {"Content-Type": "application/json"}
        self.status_code = 200


class Request:
    def __init__(self, url: str, payload: object) -> None:
        self.url = url
        self.method = "GET"
        self.response = Response(payload)


class Driver:
    def __init__(self, requests: list[Request]) -> None:
        self.requests = requests


def test_capture_keeps_only_supported_same_host_json_and_normalizes_patient_id() -> None:
    driver = Driver(
        [
            Request(
                "https://drk.test/PatientDashboard/GetPatientDemographics/123",
                {"data": {"id": 123, "fullName": "Synthetic Patient"}},
            ),
            Request(
                "https://drk.test/PatientDashboard/GetEncounters/123?page=1",
                {"data": [{"encounterId": 9, "visitStatus": "Seen"}]},
            ),
            Request("https://other.test/PatientDashboard/GetEncounters/123", {"secret": True}),
            Request("https://drk.test/unrelated", {"ignored": True}),
        ]
    )

    cards = capture_dashboard_cards(driver, allowed_host="drk.test", patient_id="123")

    assert cards["patient_information"]["record_count"] == 1
    assert cards["encounters"]["record_count"] == 1
    assert cards["pipeline"]["record_count"] == 0
    endpoint = cards["patient_information"]["records"][0]["endpoint"]
    assert "123" not in endpoint["url"]
    assert "{patientId}" in endpoint["url"]
