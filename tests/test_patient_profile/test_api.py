from __future__ import annotations

from patient_profile.api import handle_get
from patient_profile.lookup import PatientLookupResult


def test_health_and_invalid_source() -> None:
    assert handle_get("/health", {}) == (200, {"ok": True})
    status, body = handle_get("/api/patient/alva-butler", {"source": "nope"})
    assert status == 400
    assert body["error"] == "invalid_source"


def test_handle_get_uses_lookup_and_slug(monkeypatch) -> None:
    def fake_lookup(slug: str, *, source: str = "all"):
        assert slug == "alva-butler"
        assert source == "monday"
        return PatientLookupResult(
            status=200,
            body={"slug": slug, "monday": {"name": "BUTLER, ALVA"}, "drk": None, "match": None, "errors": []},
        )

    monkeypatch.setattr("patient_profile.api.lookup_patient_fn", fake_lookup)
    status, body = handle_get("/api/patient/alva-butler", {"source": "monday"})
    assert status == 200
    assert body["monday"]["name"] == "BUTLER, ALVA"
