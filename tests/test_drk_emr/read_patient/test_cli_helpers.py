from __future__ import annotations

import gzip
import zlib

from drk_emr.read_patient.cli import (
    _build_urls,
    _decode_response_body,
    _extract_patient_id_from_url,
    _is_json_response,
    _run_lifetime_probe,
    _safe_patient_folder_name,
)


class _Resp:
    def __init__(self, body: bytes, headers: dict[str, str], status_code: int = 200) -> None:
        self.body = body
        self.headers = headers
        self.status_code = status_code


class _Req:
    def __init__(self, url: str, response: _Resp | None) -> None:
        self.url = url
        self.response = response


def test_is_json_response_filters_host_and_type() -> None:
    req_ok = _Req("https://drkemr.com/api/x", _Resp(b"{}", {"Content-Type": "application/json"}))
    assert _is_json_response(req_ok, "drkemr.com")

    req_other_host = _Req("https://cdn.example.com/x", _Resp(b"{}", {"Content-Type": "application/json"}))
    assert not _is_json_response(req_other_host, "drkemr.com")

    req_non_json = _Req("https://drkemr.com/x", _Resp(b"<html/>", {"Content-Type": "text/html"}))
    assert not _is_json_response(req_non_json, "drkemr.com")


def test_decode_response_body_handles_gzip_and_deflate() -> None:
    original = b'{"ok":true}'
    gz = gzip.compress(original)
    df = zlib.compress(original)

    assert _decode_response_body(_Resp(gz, {"Content-Encoding": "gzip"})) == original
    assert _decode_response_body(_Resp(df, {"Content-Encoding": "deflate"})) == original
    assert _decode_response_body(_Resp(original, {})) == original


def test_lifetime_probe_uses_interval_deltas(monkeypatch) -> None:
    sleeps: list[int] = []

    def fake_sleep(seconds: int) -> None:
        sleeps.append(seconds)

    class FakeResp:
        status_code = 200
        headers = {"Content-Type": "application/json"}
        text = "{}"

    class FakeSession:
        def get(self, *_args, **_kwargs):
            return FakeResp()

    monkeypatch.setattr("drk_emr.read_patient.cli.time.sleep", fake_sleep)
    obs = _run_lifetime_probe(FakeSession(), "https://drkemr.com/api/x", {}, [5, 10, 15])
    assert [item["minutes_after_login"] for item in obs] == [5, 10, 15]
    assert sleeps == [300, 300, 300]


def test_build_urls_accepts_full_login_url() -> None:
    login, patient = _build_urls("https://drkemr.com/Login/LoginView", "55215")
    assert login == "https://drkemr.com/Login/LoginView"
    assert patient == "https://drkemr.com/PatientDashboard/Index/?patientId=55215"


def test_build_urls_without_patient_id_returns_home() -> None:
    login, home = _build_urls("https://drkemr.com/Login/LoginView")
    assert login == "https://drkemr.com/Login/LoginView"
    assert home == "https://drkemr.com/Dashboard"


def test_extract_patient_id_from_url() -> None:
    assert _extract_patient_id_from_url("https://drkemr.com/PatientDashboard/Index?patientId=4565") == "4565"
    assert _extract_patient_id_from_url("https://drkemr.com/PatientDashboard/Index/?patientId=4565&x=1") == "4565"
    assert _extract_patient_id_from_url("https://drkemr.com/Dashboard") is None


def test_safe_patient_folder_name() -> None:
    assert _safe_patient_folder_name("Alva Butler") == "Alva_Butler"
    assert _safe_patient_folder_name(None, "55125") == "patient_55125"
