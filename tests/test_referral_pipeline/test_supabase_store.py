from __future__ import annotations

from datetime import datetime, timezone

from referral_pipeline.monitoring.models import PatientLink
from referral_pipeline.monitoring.supabase_store import SupabaseWorkflowStore


NOW = datetime(2026, 8, 6, tzinfo=timezone.utc)


def test_patient_link_upsert_preserves_existing_cross_system_id(monkeypatch) -> None:
    store = SupabaseWorkflowStore(url="https://example.supabase.co", service_role_key="test-key")
    calls: list[tuple[str, str, dict]] = []

    def fake_request(method, table, **kwargs):
        calls.append((method, table, kwargs))
        if method == "GET":
            return [{"entity_id": "referral:1", "drk_patient_id": "drk-9"}]
        return []

    monkeypatch.setattr(store, "_request", fake_request)

    store.upsert_patient_link(
        PatientLink(
            entity_id="referral:1",
            monday_item_id="monday-7",
            updated_at=NOW,
        )
    )

    _, table, request = calls[1]
    assert table == "wcw_patient_links"
    assert request["json_body"]["monday_item_id"] == "monday-7"
    assert request["json_body"]["drk_patient_id"] == "drk-9"
    assert request["params"] == {"on_conflict": "entity_id"}


def test_find_entity_id_uses_available_external_id(monkeypatch) -> None:
    store = SupabaseWorkflowStore(url="https://example.supabase.co", service_role_key="test-key")
    seen: list[dict] = []

    def fake_request(method, table, **kwargs):
        seen.append(kwargs["params"])
        return [{"entity_id": "referral:1"}]

    monkeypatch.setattr(store, "_request", fake_request)

    assert store.find_entity_id(monday_item_id="monday-7") == "referral:1"
    assert seen[0]["monday_item_id"] == "eq.monday-7"


def test_list_patient_links_paginates_past_supabase_default(monkeypatch) -> None:
    store = SupabaseWorkflowStore(url="https://example.supabase.co", service_role_key="test-key")
    ranges = []
    rows = [
        {
            "entity_id": f"referral:{index}",
            "monday_item_id": f"monday:{index}",
            "drk_patient_id": str(index),
            "updated_at": NOW.isoformat(),
        }
        for index in range(1001)
    ]

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def json(self):
            return self.payload

    def fake_request_raw(_method, _table, **kwargs):
        requested = kwargs["extra_headers"]["Range"]
        ranges.append(requested)
        start, end = (int(value) for value in requested.split("-"))
        return Response(rows[start : end + 1])

    monkeypatch.setattr(store, "_request_raw", fake_request_raw)

    links = store.list_patient_links()

    assert len(links) == 1001
    assert ranges == ["0-999", "1000-1999"]
