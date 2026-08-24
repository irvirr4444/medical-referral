from __future__ import annotations

import http.client
import json
import threading
from datetime import datetime, timezone
from http import HTTPStatus
from unittest.mock import Mock

import pytest

from referral_pipeline.api.server import create_server
from referral_pipeline.api.webhook_server import (
    MondayWebhookHandler,
    _safe_request_log_label,
    create_webhook_server,
)
from referral_pipeline.monitoring.config import load_monitoring_config
from referral_pipeline.monitoring.sqlite_store import SQLiteWorkflowStore
from referral_pipeline.monitoring.webhook import (
    STAGE_WEBHOOK_COLUMN_ALIASES,
    WebhookAuthError,
    handle_webhook_payload,
    verify_webhook_token,
)
from referral_pipeline.integrations.monday.webhook_contract import parse_webhook_payload
from referral_pipeline.integrations.monday.webhook_registry import (
    MondayWebhookRegistry,
    MondayWebhookSubscription,
)
from referral_pipeline.integrations.monday.write_gateway import (
    MondayWriteGateway,
    MondayWritePolicy,
)
from referral_pipeline.workflow.attention import workflow_attention
from referral_pipeline.workflow.service import WorkflowExecutionService


NOW = datetime(2026, 8, 21, 1, 0, tzinfo=timezone.utc)  # 18:00 Pacific -- past the 17:00 EOD cutoff
SCHEDULED_STATUS_COLUMN = "color_mkq3gga"


def test_public_webhook_health_route_returns_json_without_logging_failure(tmp_path) -> None:
    server = create_webhook_server(
        host="127.0.0.1",
        port=0,
        database_backend="sqlite",
        sqlite_path=tmp_path / "workflow.sqlite",
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[:2]
        conn = http.client.HTTPConnection(host, int(port), timeout=5)
        conn.request("GET", "/health")
        response = conn.getresponse()
        payload = json.loads(response.read())
        conn.close()
    finally:
        server.shutdown()
        server.server_close()

    assert response.status == HTTPStatus.OK
    assert payload == {"status": "ok", "service": "monday-webhook"}


def test_public_webhook_logs_only_sanitized_processing_result(monkeypatch) -> None:
    logged: list[str] = []
    monkeypatch.setattr("builtins.print", lambda message, **_kwargs: logged.append(message))
    handler = object.__new__(MondayWebhookHandler)

    handler._log_processing_result(
        {
            "processed": True,
            "item_id": "item-1",
            "column_id": "status-column",
            "report": {"patient_name": "Must Not Be Logged"},
            "event_key": "internal-event-key",
        }
    )

    assert len(logged) == 1
    assert json.loads(logged[0]) == {
        "event": "monday_webhook_result",
        "processed": True,
        "item_id": "item-1",
        "column_id": "status-column",
    }


def test_public_webhook_logs_ignored_reason_without_payload(monkeypatch) -> None:
    logged: list[str] = []
    monkeypatch.setattr("builtins.print", lambda message, **_kwargs: logged.append(message))
    handler = object.__new__(MondayWebhookHandler)

    handler._log_processing_result({"ignored": "board_id_missing", "board_id": "secret-board"})

    assert json.loads(logged[0]) == {
        "event": "monday_webhook_result",
        "processed": False,
        "ignored": "board_id_missing",
    }


def test_public_webhook_request_labels_do_not_expose_query_tokens() -> None:
    assert _safe_request_log_label("GET", "/health") == "GET /health"
    assert (
        _safe_request_log_label("POST", "/api/monday/webhook?token=must-not-appear")
        == "POST /api/monday/webhook"
    )
    assert _safe_request_log_label("GET", "/unknown?secret=must-not-appear") == "GET other route"
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
        {
            "event": {
                "type": "update_column_value",
                "boardId": "5815942462",
                "pulseId": "item-1",
                "columnId": SCHEDULED_STATUS_COLUMN,
                "triggerUuid": "trigger-1",
            }
        },
        store=store,
        config=load_monitoring_config(),
        expected_board_id="5815942462",
        now=NOW,
        fetch_items_fn=fetch,
    )
    assert result["processed"] is True
    assert result["report"]["scheduling"]

    payload = workflow_attention(store, now=NOW, stage=5)
    exceptions = [item for item in payload["items"] if item["source"] == "exception"]
    assert len(exceptions) == 1
    assert exceptions[0]["step_id"] == "check-scheduling-status"


def test_stage_webhook_allowlist_contains_all_eod_inputs() -> None:
    assert {
        "sent_to_cm",
        "due_date",
        "appointment_date",
        "scheduling_complete",
        "scheduled_status",
    }.issubset(STAGE_WEBHOOK_COLUMN_ALIASES[5])


def test_webhook_event_can_be_rejected_by_board() -> None:
    result = parse_webhook_payload(
        {"event": {"pulseId": "item-1", "columnId": SCHEDULED_STATUS_COLUMN, "boardId": "other"}},
        expected_board_id="5815942462",
    )
    assert result == {"ignored": "board_not_tracked", "board_id": "other"}


def test_webhook_event_type_is_filtered_before_fetching() -> None:
    result = parse_webhook_payload(
        {
            "event": {
                "pulseId": "item-1",
                "columnId": SCHEDULED_STATUS_COLUMN,
                "type": "create_pulse",
            }
        }
    )
    assert result["ignored"] == "event_type_not_tracked"


def test_documented_update_column_value_event_is_normalized() -> None:
    result = parse_webhook_payload(
        {
            "event": {
                "type": "update_column_value",
                "boardId": "5815942462",
                "pulseId": "item-1",
                "columnId": SCHEDULED_STATUS_COLUMN,
                "triggerUuid": "trigger-1",
            }
        },
        expected_board_id="5815942462",
    )

    assert not isinstance(result, dict)
    assert result.event_type == "change_column_value"
    assert result.event_key == "monday-webhook:trigger-1"
    assert result.item_id == "item-1"
    assert result.column_id == SCHEDULED_STATUS_COLUMN


def test_repeated_webhook_delivery_is_deduplicated(tmp_path) -> None:
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    fetch = Mock(side_effect=_fake_fetch({"item-1": _monday_item()}))
    payload = {"event": {"pulseId": "item-1", "columnId": SCHEDULED_STATUS_COLUMN, "id": "evt-1"}}

    first = handle_webhook_payload(
        payload,
        store=store,
        config=load_monitoring_config(),
        now=NOW,
        fetch_items_fn=fetch,
    )
    second = handle_webhook_payload(
        payload,
        store=store,
        config=load_monitoring_config(),
        now=NOW,
        fetch_items_fn=fetch,
    )

    assert first["processed"] is True
    assert second["ignored"] == "duplicate_event"
    fetch.assert_called_once_with(ids=["item-1"])


def test_verify_webhook_token_rejects_missing_secret() -> None:
    with pytest.raises(WebhookAuthError):
        verify_webhook_token("anything", expected=None)


def test_verify_webhook_token_rejects_mismatch() -> None:
    with pytest.raises(WebhookAuthError):
        verify_webhook_token("wrong", expected="correct")


def test_verify_webhook_token_accepts_match() -> None:
    verify_webhook_token("correct", expected="correct")  # does not raise


def test_verify_webhook_token_accepts_header_without_query_token() -> None:
    verify_webhook_token(None, header_token="correct", expected="correct")


def test_webhook_registry_is_explicit_and_injectable() -> None:
    calls = []

    def fake_graphql(query, *, variables):
        calls.append((query, variables))
        if "create_webhook" in query:
            return {"data": {"create_webhook": {"id": "wh-1"}}}
        return {"data": {"delete_webhook": {"id": "wh-1"}}}

    registry = MondayWebhookRegistry(graphql=fake_graphql)
    created = registry.create(
        MondayWebhookSubscription(board_id="5815942462", callback_url="https://example.test/hook?token=x")
    )
    deleted = registry.delete(created["id"])

    assert created == {"id": "wh-1"}
    assert deleted == {"id": "wh-1"}
    assert calls[0][1]["boardId"] == "5815942462"
    assert calls[1][1] == {"id": "wh-1"}


def test_monday_write_gateway_is_disabled_by_default() -> None:
    gateway = MondayWriteGateway(MondayWritePolicy(board_id="5815942462"))
    with pytest.raises(PermissionError, match="disabled"):
        gateway.change_columns(
            item_id="item-1",
            stage=5,
            values_by_alias={"scheduled_status": {"label": "Scheduled"}},
            confirm=True,
        )


def test_monday_write_gateway_requires_stage_allowlist_and_confirmation() -> None:
    calls = []

    def fake_graphql(query, *, variables):
        calls.append((query, variables))
        return {"data": {"change_multiple_column_values": {"id": "item-1"}}}

    gateway = MondayWriteGateway(
        MondayWritePolicy(
            board_id="5815942462",
            enabled=True,
            stage_columns={5: frozenset({"scheduled_status"})},
        ),
        graphql=fake_graphql,
    )
    with pytest.raises(PermissionError, match="explicit confirmation"):
        gateway.change_columns(
            item_id="item-1",
            stage=5,
            values_by_alias={"scheduled_status": {"label": "Scheduled"}},
        )

    result = gateway.change_columns(
        item_id="item-1",
        stage=5,
        values_by_alias={"scheduled_status": {"label": "Scheduled"}},
        confirm=True,
    )
    assert result == {"id": "item-1"}
    assert json.loads(calls[0][1]["columnValues"]) == {"color_mkq3gga": {"label": "Scheduled"}}


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
