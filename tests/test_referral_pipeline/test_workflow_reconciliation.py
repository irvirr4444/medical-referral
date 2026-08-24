from __future__ import annotations

from datetime import datetime, timezone

import pytest

from drk_emr.create_patient import fill as drk_fill
from referral_pipeline.monitoring.models import WorkflowCase, WorkflowEvent
from referral_pipeline.monitoring.sqlite_store import SQLiteWorkflowStore
from referral_pipeline.workflow import drk_prefill
from referral_pipeline.workflow.handoff import create_monday_record, notify_case_manager, prefill_drk_chart
from referral_pipeline.workflow.service import WorkflowExecutionError, WorkflowExecutionService


NOW = datetime(2026, 8, 14, tzinfo=timezone.utc)
MANAGERS = [
    {"name": "Case Manager One", "email": "one@example.test"},
    {"name": "Case Manager Two", "email": "two@example.test"},
]


class FailAfter:
    def __init__(self, inner, method: str, after: int = 1) -> None:
        self._inner = inner
        self._method = method
        self._after = after
        self.calls = 0
        self.armed = True

    def __getattr__(self, name: str):
        attr = getattr(self._inner, name)
        if name != self._method or not callable(attr):
            return attr

        def wrapper(*args, **kwargs):
            result = attr(*args, **kwargs)
            if self.armed:
                self.calls += 1
                if self.calls >= self._after:
                    self.armed = False
                    raise RuntimeError(f"injected failure after {name}")
            return result

        return wrapper


def _completed_stage_one(store: SQLiteWorkflowStore, *, outcome: str = "reached") -> WorkflowCase:
    case = WorkflowCase(
        case_id="case-synthetic",
        source_ref="message:attachment",
        source="outlook-graph",
        patient_label="Synthetic Patient",
        referral_id="ref_test",
        current_stage=1,
        status="completed",
        created_at=NOW,
        updated_at=NOW,
        completed_at=NOW,
    )
    store.upsert_workflow_case(case)
    store.record_event(
        WorkflowEvent(
            event_key="received",
            event_type="referral_received",
            entity_id=case.case_id,
            source="outlook",
            occurred_at=NOW,
            details={"message_id": "source-message-1"},
        )
    )
    store.record_event(
        WorkflowEvent(
            event_key="contact-confirmed",
            event_type="partner_contact_confirmed",
            entity_id=case.case_id,
            source="outlook",
            occurred_at=NOW,
            details={"contact_outcome": outcome},
        )
    )
    store.record_event(
        WorkflowEvent(
            event_key="extracted",
            event_type="extraction_completed",
            entity_id=case.case_id,
            source="extractor",
            occurred_at=NOW,
            details={"fields": {"patient_name": "Synthetic Patient", "patient_dob": "01/02/1960"}},
        )
    )
    return case


@pytest.mark.parametrize("method", ["upsert_work_item", "upsert_workflow_case", "record_event"])
def test_start_assignment_repairs_each_partial_write(tmp_path, method) -> None:
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    case = _completed_stage_one(store)
    failing = FailAfter(store, method)
    service = WorkflowExecutionService(failing, case_managers=MANAGERS)

    with pytest.raises(RuntimeError, match="injected failure"):
        service.start_assignment(case.case_id, contact_outcome="reached")

    repaired = WorkflowExecutionService(store, case_managers=MANAGERS)
    repaired.start_assignment(case.case_id, contact_outcome="reached")
    assert repaired.start_assignment(case.case_id, contact_outcome="reached") is False
    stored = store.workflow_case(case.case_id)
    assert stored is not None
    assert stored.current_stage == 2
    assert stored.status == "awaiting_assignment"
    items = store.list_work_items(case_id=case.case_id, stage=2)
    assert len(items) == 1


@pytest.mark.parametrize(
    "method,after",
    [
        ("record_decision", 1),
        ("upsert_work_item", 1),
        ("upsert_workflow_case", 1),
        ("record_event", 1),
        ("upsert_external_operation", 1),
        ("upsert_external_operation", 2),
        ("upsert_external_operation", 3),
    ],
)
def test_confirm_assignment_repairs_each_partial_write(tmp_path, method, after) -> None:
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    case = _completed_stage_one(store)
    WorkflowExecutionService(store, case_managers=MANAGERS).start_assignment(
        case.case_id, contact_outcome="reached"
    )
    failing = FailAfter(store, method, after=after)
    service = WorkflowExecutionService(failing, case_managers=MANAGERS)

    with pytest.raises(RuntimeError, match="injected failure"):
        service.confirm_assignment(
            case.case_id,
            case_manager_email="one@example.test",
            decided_by="demo-operator",
        )

    repaired = WorkflowExecutionService(store, case_managers=MANAGERS)
    payload = repaired.confirm_assignment(
        case.case_id,
        case_manager_email="one@example.test",
        decided_by="demo-operator",
    )
    again = repaired.confirm_assignment(
        case.case_id,
        case_manager_email="one@example.test",
        decided_by="demo-operator",
    )
    assert payload["status"] == again["status"] == "completed"
    assert len(store.list_decisions(case.case_id)) == 1
    assert {operation.operation_type for operation in store.list_external_operations(case.case_id)} == {
        "notify-assigned-case-manager",
        "create-monday-record",
        "prefill-drk-chart",
    }
    updated = store.workflow_case(case.case_id)
    assert updated is not None
    assert updated.current_stage == 3
    for operation in store.list_external_operations(case.case_id):
        assert operation.request_payload["case_manager"]["email"] == "one@example.test"
        assert operation.request_payload["normalized"]["patient_name"] == "Synthetic Patient"
        assert operation.request_payload["source_message_id"] == "source-message-1"
        assert operation.request_payload["automatic_submit"] is False


def test_duplicate_confirmations_do_not_duplicate_side_effects(tmp_path) -> None:
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    case = _completed_stage_one(store)
    service = WorkflowExecutionService(store, case_managers=MANAGERS)
    service.start_assignment(case.case_id, contact_outcome="reached")
    service.confirm_assignment(
        case.case_id, case_manager_email="one@example.test", decided_by="demo-operator"
    )
    service.confirm_assignment(
        case.case_id, case_manager_email="one@example.test", decided_by="demo-operator"
    )
    assert len(store.list_decisions(case.case_id)) == 1
    assert len(store.list_external_operations(case.case_id)) == 3


def test_one_failed_stage_three_operation_retries_without_repeating_success(tmp_path, monkeypatch) -> None:
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    case = _completed_stage_one(store)
    service = WorkflowExecutionService(store, case_managers=MANAGERS)
    service.start_assignment(case.case_id, contact_outcome="reached")
    service.confirm_assignment(
        case.case_id, case_manager_email="one@example.test", decided_by="demo-operator"
    )
    operations = {item.operation_type: item for item in store.list_external_operations(case.case_id)}
    store.upsert_external_operation(
        operations["notify-assigned-case-manager"].model_copy(
            update={
                "request_payload": {
                    **operations["notify-assigned-case-manager"].request_payload,
                    "source_message_id": "source-1",
                }
            }
        )
    )
    store.upsert_external_operation(
        operations["create-monday-record"].model_copy(
            update={
                "request_payload": {
                    **operations["create-monday-record"].request_payload,
                    "monday_preview": {
                        "operation": "create_item",
                        "board_id": 1,
                        "group_id": "topics",
                        "item_name": "Synthetic Patient",
                        "blocked": False,
                    },
                }
            }
        )
    )
    store.upsert_external_operation(
        operations["prefill-drk-chart"].model_copy(
            update={
                "request_payload": {
                    **operations["prefill-drk-chart"].request_payload,
                    "drk_draft": {"ready_for_fill": True, "payload": {}, "blockers": []},
                }
            }
        )
    )

    class Mailbox:
        def send_reply(self, **kwargs):
            raise RuntimeError("notify failed")

    with pytest.raises(WorkflowExecutionError, match="outcome is uncertain"):
        service.execute_handoff_operation(
            case.case_id,
            "notify-assigned-case-manager",
            execute=True,
            mailbox=Mailbox(),
        )
    monday = service.execute_handoff_operation(
        case.case_id,
        "create-monday-record",
        confirm_monday_write=False,
    )
    class FakeDrk:
        def preview(self, payload):
            return {"filled": False, "would_prefill": True, "populated_fields": [], "submitted": False}

        def execute(self, payload):
            return {
                "filled": True,
                "submitted": False,
                "stopped_before": "Create/Submit",
                "populated_fields": ["firstName"],
                "current_url": "https://emr.example/PatientIntake/Index",
            }

        def inspect(self, payload):
            return {"filled": True, "populated_fields": ["firstName"]}

    drk = service.execute_handoff_operation(
        case.case_id, "prefill-drk-chart", execute=True, drk_executor=FakeDrk()
    )
    assert monday["mode"] == "preview"
    assert monday["consumed"] is False
    assert monday["status"] == "ready"
    assert monday["preview"]["written"] is False
    assert monday["preview"]["dry_run"] is True
    assert drk["status"] == "succeeded"
    assert drk["result"]["submitted"] is False
    assert drk["result"]["filled"] is True

    sent = []

    class WorkingMailbox:
        def send_reply(self, **kwargs):
            sent.append(kwargs)

    retried = service.execute_handoff_operation(
        case.case_id,
        "notify-assigned-case-manager",
        execute=True,
        mailbox=WorkingMailbox(),
        operator_retry=True,
    )
    assert retried["status"] == "succeeded"
    assert len(sent) == 1
    unchanged = {item.operation_type: item for item in store.list_external_operations(case.case_id)}
    assert unchanged["create-monday-record"].attempts == 0
    assert unchanged["create-monday-record"].status == "ready"
    assert unchanged["prefill-drk-chart"].attempts == 1
    assert unchanged["notify-assigned-case-manager"].attempts == 2


def test_handoff_executors_are_safe_by_default() -> None:
    notify = notify_case_manager(
        {"case_manager": {"name": "One", "email": "one@example.test"}, "patient_label": "Patient"}
    )
    monday = create_monday_record(
        {
            "monday_preview": {
                "operation": "create_item",
                "board_id": 1,
                "group_id": "topics",
                "item_name": "Patient",
                "blocked": False,
            }
        }
    )
    drk = prefill_drk_chart({"drk_draft": {"ready_for_fill": True, "payload": {}, "blockers": []}})
    assert notify["sent"] is False
    assert monday["written"] is False
    assert monday["dry_run"] is True
    assert drk["submitted"] is False
    assert drk["filled"] is False
    assert drk["stopped_before"] == "Create/Submit"


def test_preview_monday_then_real_write_invokes_executor_once(tmp_path, monkeypatch) -> None:
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    case = _completed_stage_one(store)
    service = WorkflowExecutionService(store, case_managers=MANAGERS)
    service.start_assignment(case.case_id, contact_outcome="reached")
    service.confirm_assignment(
        case.case_id, case_manager_email="one@example.test", decided_by="demo-operator"
    )
    operations = {item.operation_type: item for item in store.list_external_operations(case.case_id)}
    store.upsert_external_operation(
        operations["create-monday-record"].model_copy(
            update={
                "request_payload": {
                    **operations["create-monday-record"].request_payload,
                    "monday_preview": {
                        "operation": "create_item",
                        "board_id": 1,
                        "group_id": "topics",
                        "item_name": "Synthetic Patient",
                        "blocked": False,
                    },
                }
            }
        )
    )
    writes = []

    def fake_apply(preview, *, on_item_created=None):
        writes.append(preview)
        item = {"id": "1234567890"}
        if on_item_created is not None:
            on_item_created(item)
        return {"item": item, "applied_actions": []}

    monkeypatch.setattr("master_sheet_writer.apply_master_sheet_create", fake_apply)
    preview = service.execute_handoff_operation(
        case.case_id, "create-monday-record", confirm_monday_write=False
    )
    assert preview["status"] == "ready"
    assert preview["consumed"] is False
    assert writes == []
    real = service.execute_handoff_operation(
        case.case_id, "create-monday-record", confirm_monday_write=True
    )
    assert real["status"] == "succeeded"
    assert real["result"]["written"] is True
    assert real["result"]["monday_item_id"] == "1234567890"
    assert len(writes) == 1
    stored = store.list_external_operations(case.case_id)
    monday = next(item for item in stored if item.operation_type == "create-monday-record")
    assert monday.attempts == 1


def test_false_preview_success_is_reopened_for_a_real_monday_write(tmp_path, monkeypatch) -> None:
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    case = _completed_stage_one(store)
    service = WorkflowExecutionService(store, case_managers=MANAGERS)
    service.start_assignment(case.case_id, contact_outcome="reached")
    service.confirm_assignment(
        case.case_id, case_manager_email="one@example.test", decided_by="demo-operator"
    )
    operation = next(
        item
        for item in store.list_external_operations(case.case_id)
        if item.operation_type == "create-monday-record"
    )
    store.upsert_external_operation(
        operation.model_copy(
            update={
                "status": "succeeded",
                "completed_at": NOW,
                "request_payload": {
                    **operation.request_payload,
                    "monday_preview": {
                        "operation": "create_item",
                        "board_id": 1,
                        "group_id": "topics",
                        "item_name": "Synthetic Patient",
                        "blocked": False,
                    },
                },
                "result": {"dry_run": True, "written": False, "would_create": True},
            }
        )
    )
    writes = []
    def fake_apply(preview, *, on_item_created=None):
        writes.append(preview)
        item = {"id": "reopened-item"}
        if on_item_created is not None:
            on_item_created(item)
        return {"item": item}

    monkeypatch.setattr("master_sheet_writer.apply_master_sheet_create", fake_apply)
    result = service.execute_handoff_operation(
        case.case_id, "create-monday-record", confirm_monday_write=True
    )
    assert result["status"] == "succeeded"
    assert result["result"]["written"] is True
    assert len(writes) == 1
    stored = next(
        item
        for item in store.list_external_operations(case.case_id)
        if item.operation_type == "create-monday-record"
    )
    assert stored.result["monday_item_id"] == "reopened-item"


def test_expired_running_lease_becomes_uncertain_and_does_not_rerun(tmp_path, monkeypatch) -> None:
    from datetime import timedelta

    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    case = _completed_stage_one(store)
    service = WorkflowExecutionService(store, case_managers=MANAGERS)
    service.start_assignment(case.case_id, contact_outcome="reached")
    service.confirm_assignment(
        case.case_id, case_manager_email="one@example.test", decided_by="demo-operator"
    )
    operation = next(
        item
        for item in store.list_external_operations(case.case_id)
        if item.operation_type == "create-monday-record"
    )
    store.upsert_external_operation(
        operation.model_copy(
            update={
                "status": "running",
                "attempts": 1,
                "lease_until": datetime(2020, 1, 1, tzinfo=timezone.utc),
                "request_payload": {
                    **operation.request_payload,
                    "monday_preview": {
                        "operation": "create_item",
                        "board_id": 1,
                        "group_id": "topics",
                        "item_name": "Synthetic Patient",
                        "blocked": False,
                    },
                },
            }
        )
    )
    writes = []
    monkeypatch.setattr(
        "master_sheet_writer.apply_master_sheet_create",
        lambda preview: writes.append(preview) or {"item": {"id": "x"}},
    )
    with pytest.raises(WorkflowExecutionError, match="uncertain"):
        service.execute_handoff_operation(
            case.case_id, "create-monday-record", confirm_monday_write=True
        )
    stored = next(
        item
        for item in store.list_external_operations(case.case_id)
        if item.operation_type == "create-monday-record"
    )
    assert stored.status == "uncertain"
    assert writes == []
    with pytest.raises(WorkflowExecutionError, match="uncertain"):
        service.execute_handoff_operation(
            case.case_id,
            "create-monday-record",
            confirm_monday_write=True,
            operator_retry=True,
        )
    assert writes == []
    del timedelta


def test_concurrent_claims_allow_only_one_runner(tmp_path) -> None:
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    case = _completed_stage_one(store)
    service = WorkflowExecutionService(store, case_managers=MANAGERS)
    service.start_assignment(case.case_id, contact_outcome="reached")
    service.confirm_assignment(
        case.case_id, case_manager_email="one@example.test", decided_by="demo-operator"
    )
    operation = next(
        item
        for item in store.list_external_operations(case.case_id)
        if item.operation_type == "notify-assigned-case-manager"
    )
    first = store.claim_external_operation(
        operation.operation_id, case_id=case.case_id, claimed_by="worker-a"
    )
    second = store.claim_external_operation(
        operation.operation_id, case_id=case.case_id, claimed_by="worker-b"
    )
    assert first == "claimed"
    assert second == "busy"


def test_drk_execute_without_populated_fields_is_not_succeeded(tmp_path) -> None:
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    case = _completed_stage_one(store)
    service = WorkflowExecutionService(store, case_managers=MANAGERS)
    service.start_assignment(case.case_id, contact_outcome="reached")
    service.confirm_assignment(
        case.case_id, case_manager_email="one@example.test", decided_by="demo-operator"
    )
    operation = next(
        item
        for item in store.list_external_operations(case.case_id)
        if item.operation_type == "prefill-drk-chart"
    )
    store.upsert_external_operation(
        operation.model_copy(
            update={
                "request_payload": {
                    **operation.request_payload,
                    "drk_draft": {
                        "ready_for_fill": True,
                        "payload": {
                            "demographics": {
                                "first_name": "Synthetic",
                                "last_name": "Patient",
                            }
                        },
                    },
                }
            }
        )
    )

    class EmptyFill:
        def prefill(self, payload):
            return {
                "filled": True,
                "populated_fields": [],
                "submitted": False,
                "stopped_before": "Create/Submit",
            }

        def inspect(self, payload):
            return {"filled": False, "populated_fields": []}

    with pytest.raises(WorkflowExecutionError, match="did not populate"):
        service.execute_handoff_operation(
            case.case_id, "prefill-drk-chart", execute=True, drk_executor=EmptyFill()
        )
    stored = next(
        item
        for item in store.list_external_operations(case.case_id)
        if item.operation_type == "prefill-drk-chart"
    )
    assert stored.status == "failed"


def test_drk_prefill_retains_browser_for_operator_review(monkeypatch) -> None:
    class Driver:
        current_url = "https://emr.example/PatientIntake/Index"
        quit_called = False

        def quit(self) -> None:
            self.quit_called = True

    driver = Driver()
    monkeypatch.setattr(
        drk_prefill,
        "_open_logged_in_driver",
        lambda: (driver, {"login": "ok"}),
    )
    monkeypatch.setattr(drk_fill, "navigate_to_patient_intake", lambda _driver: None)
    monkeypatch.setattr(
        drk_fill,
        "fill_intake_draft",
        lambda _driver, _draft: {"populated_fields": ["firstName", "lastName"]},
    )
    monkeypatch.setattr(drk_fill, "assert_create_patient_untouched", lambda _driver: None)
    payload = {
        "case_id": "case-retained-session",
        "drk_draft": {
            "ready_for_fill": True,
            "payload": {
                "demographics": {
                    "first_name": "Synthetic",
                    "last_name": "Patient",
                }
            },
        },
    }
    adapter = drk_prefill.SeleniumDrkPrefillAdapter()

    result = adapter.prefill(payload)

    assert result["session_retained"] is True
    assert driver.quit_called is False
    assert adapter.inspect(payload)["filled"] is True
    drk_prefill._close_session("case-retained-session")
    assert driver.quit_called is True


def test_crash_before_success_persist_does_not_repeat_while_lease_held(tmp_path, monkeypatch) -> None:
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    case = _completed_stage_one(store)
    inner_service = WorkflowExecutionService(store, case_managers=MANAGERS)
    inner_service.start_assignment(case.case_id, contact_outcome="reached")
    inner_service.confirm_assignment(
        case.case_id, case_manager_email="one@example.test", decided_by="demo-operator"
    )
    operation = next(
        item
        for item in store.list_external_operations(case.case_id)
        if item.operation_type == "create-monday-record"
    )
    store.upsert_external_operation(
        operation.model_copy(
            update={
                "request_payload": {
                    **operation.request_payload,
                    "monday_preview": {
                        "operation": "create_item",
                        "board_id": 1,
                        "group_id": "topics",
                        "item_name": "Synthetic Patient",
                        "blocked": False,
                    },
                }
            }
        )
    )
    writes = []
    def fake_apply(preview, *, on_item_created=None):
        writes.append(preview)
        item = {"id": "crash-item"}
        if on_item_created is not None:
            on_item_created(item)
        return {"item": item}

    monkeypatch.setattr("master_sheet_writer.apply_master_sheet_create", fake_apply)

    class CrashBeforeSuccess:
        def __init__(self, inner) -> None:
            self._inner = inner

        def __getattr__(self, name: str):
            return getattr(self._inner, name)

        def upsert_external_operation(self, operation):
            if operation.status == "succeeded" and operation.operation_type == "create-monday-record":
                raise RuntimeError("crash before persist")
            return self._inner.upsert_external_operation(operation)

    crashing = WorkflowExecutionService(CrashBeforeSuccess(store), case_managers=MANAGERS)
    with pytest.raises(WorkflowExecutionError, match="is uncertain"):
        crashing.execute_handoff_operation(
            case.case_id, "create-monday-record", confirm_monday_write=True
        )
    assert len(writes) == 1
    stored = next(
        item
        for item in store.list_external_operations(case.case_id)
        if item.operation_type == "create-monday-record"
    )
    assert stored.status == "uncertain"
    assert stored.result["monday_item_id"] == "crash-item"
    reconciled = WorkflowExecutionService(store, case_managers=MANAGERS).execute_handoff_operation(
        case.case_id, "create-monday-record", confirm_monday_write=True
    )
    assert reconciled["mode"] == "reconciled"
    assert reconciled["status"] == "succeeded"
    assert len(writes) == 1


def test_uncertain_monday_reconciles_from_item_id_without_rewrite(tmp_path, monkeypatch) -> None:
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    case = _completed_stage_one(store)
    service = WorkflowExecutionService(store, case_managers=MANAGERS)
    service.start_assignment(case.case_id, contact_outcome="reached")
    service.confirm_assignment(
        case.case_id, case_manager_email="one@example.test", decided_by="demo-operator"
    )
    operation = next(
        item
        for item in store.list_external_operations(case.case_id)
        if item.operation_type == "create-monday-record"
    )
    store.upsert_external_operation(
        operation.model_copy(
            update={
                "status": "uncertain",
                "result": {"written": True, "monday_item_id": "already-created"},
                "last_error": "running lease expired; external outcome is unknown",
            }
        )
    )
    writes = []
    monkeypatch.setattr(
        "master_sheet_writer.apply_master_sheet_create",
        lambda preview: writes.append(preview) or {"item": {"id": "should-not-run"}},
    )
    result = service.execute_handoff_operation(
        case.case_id, "create-monday-record", confirm_monday_write=True
    )
    assert result["mode"] == "reconciled"
    assert result["status"] == "succeeded"
    assert writes == []
    stored = next(
        item
        for item in store.list_external_operations(case.case_id)
        if item.operation_type == "create-monday-record"
    )
    assert stored.status == "succeeded"
    assert stored.result["monday_item_id"] == "already-created"
