from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "supabase"
    / "migrations"
    / "202608120001_create_stage_one_workflow.sql"
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
