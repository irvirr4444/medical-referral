-- Durable execution state shared by Stages 2-7. Stage-specific clinical and
-- destination data remains in its source system or existing review snapshot.

alter table public.wcw_workflow_cases
    drop constraint if exists wcw_workflow_cases_status_check;

alter table public.wcw_workflow_cases
    add constraint wcw_workflow_cases_status_check
    check (
        status in (
            'discovered',
            'processing',
            'awaiting_partner_contact',
            'needs_attention',
            'completed',
            'failed',
            'awaiting_assignment',
            'awaiting_handoff',
            'handoff_in_progress',
            'handoff_blocked'
        )
    ) not valid;

alter table public.wcw_workflow_cases
    validate constraint wcw_workflow_cases_status_check;

create table if not exists public.wcw_work_items (
    work_item_id text primary key,
    case_id text not null references public.wcw_workflow_cases(case_id) on delete cascade,
    stage smallint not null check (stage between 2 and 7),
    step_id text not null check (length(trim(step_id)) > 0),
    owner_role text not null
        check (owner_role in ('case_manager', 'intake_team', 'system')),
    status text not null
        check (status in ('waiting', 'ready', 'completed', 'blocked', 'failed')),
    recommended_assignee text,
    recommendation_reason text,
    assigned_to text,
    payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    completed_at timestamptz,
    unique (case_id, stage, step_id),
    check (updated_at >= created_at),
    check (completed_at is null or completed_at >= created_at)
);

create index if not exists idx_wcw_work_items_queue
    on public.wcw_work_items (stage, status, updated_at desc);

create table if not exists public.wcw_workflow_decisions (
    decision_id text primary key,
    idempotency_key text not null unique,
    case_id text not null references public.wcw_workflow_cases(case_id) on delete cascade,
    stage smallint not null check (stage between 2 and 7),
    step_id text not null check (length(trim(step_id)) > 0),
    decision_type text not null check (length(trim(decision_type)) > 0),
    selected_value jsonb not null,
    decided_by text not null check (length(trim(decided_by)) > 0),
    created_at timestamptz not null default now()
);

create index if not exists idx_wcw_workflow_decisions_case
    on public.wcw_workflow_decisions (case_id, created_at desc);

create table if not exists public.wcw_external_operations (
    operation_id text primary key,
    idempotency_key text not null unique,
    case_id text not null references public.wcw_workflow_cases(case_id) on delete cascade,
    stage smallint not null check (stage between 2 and 7),
    operation_type text not null check (length(trim(operation_type)) > 0),
    status text not null
        check (status in ('ready', 'running', 'succeeded', 'blocked', 'failed')),
    request_payload jsonb not null default '{}'::jsonb,
    result jsonb not null default '{}'::jsonb,
    attempts integer not null default 0 check (attempts >= 0),
    last_error text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    completed_at timestamptz,
    check (updated_at >= created_at),
    check (completed_at is null or completed_at >= created_at)
);

create index if not exists idx_wcw_external_operations_case
    on public.wcw_external_operations (case_id, stage, updated_at desc);

alter table public.wcw_work_items enable row level security;
alter table public.wcw_workflow_decisions enable row level security;
alter table public.wcw_external_operations enable row level security;

revoke all on public.wcw_work_items from anon, authenticated;
revoke all on public.wcw_workflow_decisions from anon, authenticated;
revoke all on public.wcw_external_operations from anon, authenticated;

grant select, insert, update, delete on public.wcw_work_items to service_role;
grant select, insert, update, delete on public.wcw_workflow_decisions to service_role;
grant select, insert, update, delete on public.wcw_external_operations to service_role;
