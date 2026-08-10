from __future__ import annotations

import json

from drk_emr.live_reader.config import DrkLiveReaderConfig
from drk_emr.live_reader.reader import DrkPatientReader


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
    def __init__(self) -> None:
        self.current_url = "about:blank"
        self.requests: list[Request] = []
        self.quit_called = False

    def get(self, url: str) -> None:
        if url.endswith("/Dashboard"):
            self.current_url = "https://drk.test/Login/LoginView"
            self.requests = []
            return
        self.current_url = url
        patient_id = url.rsplit("=", 1)[-1]
        self.requests = [
            Request(
                f"https://drk.test/PatientDashboard/GetPatientDemographics/{patient_id}",
                {"data": {"id": int(patient_id), "fullName": "Synthetic Patient"}},
            )
        ]

    def quit(self) -> None:
        self.quit_called = True


def test_reader_reuses_one_authenticated_driver_for_batch(tmp_path) -> None:
    driver = Driver()
    factory_calls = []
    login_calls = []

    def factory(config):
        factory_calls.append(config)
        return driver

    def fake_login(current, _url, _username, _password):
        login_calls.append(True)
        current.current_url = "https://drk.test/Dashboard"

    config = DrkLiveReaderConfig(
        emr_url="https://drk.test",
        username="test-user",
        password="test-password",
        profile_dir=tmp_path / "profile",
        headless=True,
        page_timeout_seconds=0.2,
        network_idle_seconds=0,
    )

    with DrkPatientReader(
        config,
        driver_factory=factory,
        login_function=fake_login,
    ) as reader:
        first = reader.read_patient("123")
        second = reader.read_patient("456")

    assert first.patient_id == "123"
    assert second.patient_id == "456"
    assert len(factory_calls) == 1
    assert len(login_calls) == 1
    assert driver.quit_called is True
