-- Additive attention deadlines for existing workflow cases and work items.
-- due_soon / overdue are never stored; they are computed from due timestamps.

alter table public.wcw_workflow_cases
    add column if not exists attention_due_at timestamptz;

alter table public.wcw_work_items
    add column if not exists due_at timestamptz;

create index if not exists idx_wcw_workflow_cases_attention_due
    on public.wcw_workflow_cases (attention_due_at)
    where attention_due_at is not null
      and status not in ('completed', 'cancelled', 'failed');

create index if not exists idx_wcw_work_items_due
    on public.wcw_work_items (due_at)
    where due_at is not null
      and status not in ('completed', 'cancelled');

-- Existing RLS remains in force: no anon or authenticated access; service_role only.
revoke all on public.wcw_workflow_cases from anon, authenticated;
revoke all on public.wcw_work_items from anon, authenticated;
grant select, insert, update, delete on public.wcw_workflow_cases to service_role;
grant select, insert, update, delete on public.wcw_work_items to service_role;
