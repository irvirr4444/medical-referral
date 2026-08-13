from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "supabase"
    / "migrations"
    / "202608120001_create_stage_one_workflow.sql"
)
HARDENING_MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "supabase"
    / "migrations"
    / "202608130001_harden_stage_one_workflow.sql"
)
EXECUTION_MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "supabase"
    / "migrations"
    / "202608130002_create_workflow_execution.sql"
)


def test_stage_one_migration_keeps_backend_tables_private() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").casefold()

    assert "enable row level security" in sql
    assert "revoke all on public.wcw_workflow_cases from anon, authenticated" in sql
    assert "revoke all on public.wcw_outbound_acknowledgements from anon, authenticated" in sql
    assert "grant execute on function public.claim_wcw_acknowledgement" in sql
    assert "to service_role" in sql


def test_attachment_hash_is_searchable_but_not_unique() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").casefold()

    assert "idx_wcw_workflow_cases_attachment_sha256" in sql
    assert "attachment_sha256 text unique" not in sql


def test_stage_one_hardening_aligns_state_and_relationships() -> None:
    sql = HARDENING_MIGRATION.read_text(encoding="utf-8").casefold()

    assert "'awaiting_partner_contact'" in sql
    assert "referral_reviews_workflow_case_fk" in sql
    assert "wcw_notification_outbox_exception_fk" in sql
    assert "check (attempts >= 0)" in sql
    assert "check (value >= 0)" in sql
    assert "not valid" in sql


def test_workflow_execution_tables_are_private_and_constrained() -> None:
    sql = EXECUTION_MIGRATION.read_text(encoding="utf-8").casefold()

    for table in (
        "wcw_work_items",
        "wcw_workflow_decisions",
        "wcw_external_operations",
    ):
        assert f"alter table public.{table} enable row level security" in sql
        assert f"revoke all on public.{table} from anon, authenticated" in sql
    assert "unique (case_id, stage, step_id)" in sql
    assert "idempotency_key text not null unique" in sql
    assert "check (attempts >= 0)" in sql
