from __future__ import annotations

import http.client
import json
import threading
from datetime import datetime, timezone
from http import HTTPStatus
from unittest.mock import Mock

import pytest

from referral_pipeline.api.server import create_server
from referral_pipeline.monitoring.config import load_monitoring_config
from referral_pipeline.monitoring.sqlite_store import SQLiteWorkflowStore
from referral_pipeline.monitoring.webhook import (
    WebhookAuthError,
    handle_webhook_payload,
    verify_webhook_token,
)
from referral_pipeline.workflow.attention import workflow_attention
from referral_pipeline.workflow.service import WorkflowExecutionService


NOW = datetime(2026, 8, 21, 1, 0, tzinfo=timezone.utc)  # 18:00 Pacific -- past the 17:00 EOD cutoff
SCHEDULED_STATUS_COLUMN = "color_mkq3gga"
NAME_COLUMN = "name"


def _monday_item(item_id: str = "item-1") -> dict:
    return {
        "id": item_id,
        "name": "Synthetic Patient",
        "updated_at": "2026-08-20T22:00:00Z",
        "group": {"id": "g1", "title": "Working pipeline"},
        "column_values": [
            {"id": SCHEDULED_STATUS_COLUMN, "text": "Not Scheduled"},
            {"id": "deal_owner", "text": "Example Manager"},
            {"id": "status7__1", "text": "Yes"},
            {"id": "date_mm2gybh5", "text": "2026-08-19"},
        ],
    }


def _fake_fetch(items_by_id: dict[str, dict]):
    def fetch(*, ids: list[str]):
        return {}, [items_by_id[item_id] for item_id in ids if item_id in items_by_id]

    return fetch


def test_challenge_handshake_is_echoed_back(tmp_path) -> None:
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    result = handle_webhook_payload(
        {"challenge": "abc123"},
        store=store,
        config=load_monitoring_config(),
    )
    assert result == {"challenge": "abc123"}


def test_untracked_column_is_ignored_without_fetching(tmp_path) -> None:
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    fetch = Mock(side_effect=AssertionError("should not fetch for an untracked column"))
    result = handle_webhook_payload(
        {"event": {"pulseId": "item-1", "columnId": "text6__1"}},
        store=store,
        config=load_monitoring_config(),
        fetch_items_fn=fetch,
    )
    assert result["ignored"] == "column_not_tracked"
    fetch.assert_not_called()


def test_tracked_column_change_creates_stage_five_exception(tmp_path) -> None:
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    fetch = _fake_fetch({"item-1": _monday_item()})
    result = handle_webhook_payload(
        {"event": {"pulseId": "item-1", "columnId": SCHEDULED_STATUS_COLUMN}},
        store=store,
        config=load_monitoring_config(),
        now=NOW,
        fetch_items_fn=fetch,
    )
    assert result["processed"] is True
    assert result["report"]["scheduling"]

    payload = workflow_attention(store, now=NOW, stage=5)
    exceptions = [item for item in payload["items"] if item["source"] == "exception"]
    assert len(exceptions) == 1
    assert exceptions[0]["step_id"] == "check-scheduling-status"


def test_verify_webhook_token_rejects_missing_secret() -> None:
    with pytest.raises(WebhookAuthError):
        verify_webhook_token("anything", expected=None)


def test_verify_webhook_token_rejects_mismatch() -> None:
    with pytest.raises(WebhookAuthError):
        verify_webhook_token("wrong", expected="correct")


def test_verify_webhook_token_accepts_match() -> None:
    verify_webhook_token("correct", expected="correct")  # does not raise


def test_server_webhook_route_requires_token(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("MONDAY_WEBHOOK_TOKEN", raising=False)
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    server = create_server(
        host="127.0.0.1",
        port=0,
        workflow_execution=WorkflowExecutionService(store, case_managers=[]),
        feed=Mock(),
        monitor=Mock(),
        handoff_mailbox_factory=lambda: None,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[:2]
        conn = http.client.HTTPConnection(host, int(port), timeout=5)
        body = json.dumps({"challenge": "x"}).encode("utf-8")
        conn.request(
            "POST",
            "/api/monday/webhook",
            body=body,
            headers={"Content-Type": "application/json"},
        )
        response = conn.getresponse()
        response.read()
        conn.close()
    finally:
        server.shutdown()
        server.server_close()
    assert response.status == HTTPStatus.FORBIDDEN


def test_server_webhook_route_echoes_challenge_with_valid_token(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MONDAY_WEBHOOK_TOKEN", "shared-secret")
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    server = create_server(
        host="127.0.0.1",
        port=0,
        workflow_execution=WorkflowExecutionService(store, case_managers=[]),
        feed=Mock(),
        monitor=Mock(),
        handoff_mailbox_factory=lambda: None,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[:2]
        conn = http.client.HTTPConnection(host, int(port), timeout=5)
        body = json.dumps({"challenge": "x"}).encode("utf-8")
        conn.request(
            "POST",
            "/api/monday/webhook?token=shared-secret",
            body=body,
            headers={"Content-Type": "application/json"},
        )
        response = conn.getresponse()
        payload = json.loads(response.read())
        conn.close()
    finally:
        server.shutdown()
        server.server_close()
    assert response.status == HTTPStatus.OK
    assert payload == {"challenge": "x"}
