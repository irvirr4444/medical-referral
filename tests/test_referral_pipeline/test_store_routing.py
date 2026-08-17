from __future__ import annotations

from datetime import datetime, timezone

from referral_pipeline.monitoring.models import WorkflowCase
from referral_pipeline.monitoring.routing import RoutingWorkflowStore, persistence_for
from referral_pipeline.monitoring.sqlite_store import SQLiteWorkflowStore
from referral_pipeline.persistence_policy import SyntheticPersistencePolicy
from referral_pipeline.review.store import ReviewStore, build_review_store
from referral_pipeline.review.workflow import create_and_send_review


NOW = datetime(2026, 8, 14, tzinfo=timezone.utc)


def test_wcw_sample_hashes_cannot_route_to_supabase(tmp_path) -> None:
    manifest = tmp_path / "dataset.json"
    manifest.write_text(
        '{"synthetic_only": true, "cases": [{"sha256": "' + ("b" * 64) + '"}]}',
        encoding="utf-8",
    )
    policy = SyntheticPersistencePolicy.from_manifest(manifest)
    wcw_sample = "a" * 64
    assert not policy.permits(wcw_sample)
    assert policy.stage_one_backend("supabase", wcw_sample) == "sqlite"
    assert policy.stage_one_backend("supabase", "b" * 64) == "supabase"


def test_router_keeps_new_local_cases_off_the_remote_store(tmp_path) -> None:
    local = SQLiteWorkflowStore(tmp_path / "local.sqlite")
    remote = SQLiteWorkflowStore(tmp_path / "remote.sqlite")
    router = RoutingWorkflowStore(local=local, remote=remote)
    case = WorkflowCase(
        case_id="case-wcw-sample",
        source_ref="local-sample",
        source="outlook-graph",
        current_stage=1,
        status="processing",
        created_at=NOW,
        updated_at=NOW,
    )
    router.upsert_workflow_case(case)
    assert local.workflow_case(case.case_id) is not None
    assert remote.workflow_case(case.case_id) is None
    assert persistence_for(router, case.case_id) == "sqlite"


def test_router_aggregates_local_and_remote_cases(tmp_path) -> None:
    local = SQLiteWorkflowStore(tmp_path / "local.sqlite")
    remote = SQLiteWorkflowStore(tmp_path / "remote.sqlite")
    local.upsert_workflow_case(
        WorkflowCase(
            case_id="case-local",
            source_ref="wcw-sample",
            source="outlook-graph",
            current_stage=1,
            status="processing",
            created_at=NOW,
            updated_at=NOW,
        )
    )
    remote.upsert_workflow_case(
        WorkflowCase(
            case_id="case-synthetic",
            source_ref="synthetic",
            source="outlook-graph",
            current_stage=2,
            status="awaiting_assignment",
            created_at=NOW,
            updated_at=NOW,
        )
    )
    router = RoutingWorkflowStore(local=local, remote=remote)
    cases = {item.case_id: item for item in router.list_workflow_cases()}
    assert set(cases) == {"case-local", "case-synthetic"}
    assert persistence_for(router, "case-local") == "sqlite"
    assert persistence_for(router, "case-synthetic") == "supabase"


def test_create_and_send_review_does_not_copy_wcw_samples_to_supabase(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("REFERRAL_REVIEW_STORE", "supabase")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-key")
    monkeypatch.setenv("SYNTHETIC_DATASET_MANIFEST", str(tmp_path / "missing.json"))

    store = build_review_store(tmp_path / "state.sqlite", allow_supabase=False)
    assert isinstance(store, ReviewStore)

    called = []

    class Mailbox:
        def send_reply(self, **kwargs):
            called.append(kwargs)

    for name in ("canonical-referral.json", "intake-plan.json", "master-sheet-preview.json", "drk-create-draft.json"):
        (tmp_path / name).write_text("{}", encoding="utf-8")
    result = create_and_send_review(
        {
            "canonical_referral_path": str(tmp_path / "canonical-referral.json"),
            "plan_path": str(tmp_path / "intake-plan.json"),
            "preview_path": str(tmp_path / "master-sheet-preview.json"),
            "drk_draft_path": str(tmp_path / "drk-create-draft.json"),
            "source_message_id": "source-1",
            "source_conversation_id": "thread-1",
            "attachment_sha256": "a" * 64,
        },
        recipient="intake@example.test",
        write_config_path=tmp_path / "canonical-referral.json",
        state_db=tmp_path / "state.sqlite",
        mailbox=Mailbox(),
        allow_supabase_store=True,
    )
    assert result["review_id"]
    assert ReviewStore(tmp_path / "state.sqlite").get(result["review_id"]).status == "awaiting_confirmation"
    assert called


def test_remote_unavailable_raises_without_explicit_fallback(tmp_path, monkeypatch) -> None:
    from referral_pipeline.monitoring.store import create_routed_workflow_store

    monkeypatch.setenv("WORKFLOW_DATABASE_BACKEND", "supabase")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    try:
        create_routed_workflow_store(sqlite_path=tmp_path / "local.sqlite", include_remote=True)
    except RuntimeError as error:
        assert "Supabase workflow store is required" in str(error)
    else:
        raise AssertionError("expected configuration error")


def test_explicit_local_fallback_returns_sqlite(tmp_path, monkeypatch) -> None:
    from referral_pipeline.monitoring.sqlite_store import SQLiteWorkflowStore
    from referral_pipeline.monitoring.store import create_routed_workflow_store

    monkeypatch.setenv("WORKFLOW_DATABASE_BACKEND", "supabase")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    store = create_routed_workflow_store(
        sqlite_path=tmp_path / "local.sqlite",
        include_remote=True,
        allow_local_fallback=True,
    )
    assert isinstance(store, SQLiteWorkflowStore)


def test_normal_aggregation_does_not_copy_local_cases(tmp_path) -> None:
    local = SQLiteWorkflowStore(tmp_path / "local.sqlite")
    remote = SQLiteWorkflowStore(tmp_path / "remote.sqlite")
    router = RoutingWorkflowStore(local=local, remote=remote)
    local.upsert_workflow_case(
        WorkflowCase(
            case_id="case-wcw",
            source_ref="sample",
            source="outlook-graph",
            current_stage=1,
            status="processing",
            created_at=NOW,
            updated_at=NOW,
        )
    )
    remote.upsert_workflow_case(
        WorkflowCase(
            case_id="case-synth",
            source_ref="synth",
            source="outlook-graph",
            current_stage=1,
            status="processing",
            created_at=NOW,
            updated_at=NOW,
        )
    )
    ids = {item.case_id for item in router.list_workflow_cases()}
    assert ids == {"case-wcw", "case-synth"}
    assert remote.workflow_case("case-wcw") is None
    assert local.workflow_case("case-synth") is None
