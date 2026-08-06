-- Backend-only operational state for WCW workflow monitoring.
-- Do not grant anon/authenticated access; the worker uses a server-side service key.

create table if not exists public.wcw_patient_links (
    entity_id text primary key,
    monday_item_id text unique,
    drk_patient_id text unique,
    patient_label text,
    identity_digest text,
    updated_at timestamptz not null
);

create table if not exists public.wcw_system_snapshots (
    id bigint generated always as identity primary key,
    source text not null check (source in ('monday', 'drk', 'schedule')),
    external_id text not null,
    observed_at timestamptz not null,
    payload_digest text not null,
    payload jsonb not null,
    unique (source, external_id, payload_digest)
);
create index if not exists idx_wcw_system_snapshots_latest
    on public.wcw_system_snapshots (source, external_id, observed_at desc);

create table if not exists public.wcw_workflow_events (
    event_key text primary key,
    event_type text not null,
    entity_id text not null,
    source text not null,
    occurred_at timestamptz not null,
    details jsonb not null default '{}'::jsonb
);

create table if not exists public.wcw_workflow_exceptions (
    exception_key text primary key,
    exception_type text not null,
    entity_id text not null,
    severity text not null check (severity in ('info', 'warning', 'critical')),
    status text not null check (status in ('open', 'resolved')),
    first_seen_at timestamptz not null,
    last_seen_at timestamptz not null,
    resolved_at timestamptz,
    details jsonb not null default '{}'::jsonb
);
create index if not exists idx_wcw_workflow_exceptions_open
    on public.wcw_workflow_exceptions (status, exception_type);

create table if not exists public.wcw_notification_outbox (
    notification_key text primary key,
    exception_key text not null,
    recipient text not null,
    subject text not null,
    body text not null,
    status text not null check (status in ('pending', 'sent', 'failed')),
    attempts integer not null default 0,
    last_error text,
    created_at timestamptz not null
);

create table if not exists public.wcw_workflow_counters (
    entity_id text not null,
    counter_name text not null,
    value integer not null,
    updated_at timestamptz not null,
    primary key (entity_id, counter_name)
);

create table if not exists public.wcw_sync_cursors (
    source text primary key,
    cursor text,
    updated_at timestamptz not null
);

alter table public.wcw_patient_links enable row level security;
alter table public.wcw_system_snapshots enable row level security;
alter table public.wcw_workflow_events enable row level security;
alter table public.wcw_workflow_exceptions enable row level security;
alter table public.wcw_notification_outbox enable row level security;
alter table public.wcw_workflow_counters enable row level security;
alter table public.wcw_sync_cursors enable row level security;

revoke all on public.wcw_patient_links from anon, authenticated;
revoke all on public.wcw_system_snapshots from anon, authenticated;
revoke all on public.wcw_workflow_events from anon, authenticated;
revoke all on public.wcw_workflow_exceptions from anon, authenticated;
revoke all on public.wcw_notification_outbox from anon, authenticated;
revoke all on public.wcw_workflow_counters from anon, authenticated;
revoke all on public.wcw_sync_cursors from anon, authenticated;

grant all on public.wcw_patient_links to service_role;
grant all on public.wcw_system_snapshots to service_role;
grant all on public.wcw_workflow_events to service_role;
grant all on public.wcw_workflow_exceptions to service_role;
grant all on public.wcw_notification_outbox to service_role;
grant all on public.wcw_workflow_counters to service_role;
grant all on public.wcw_sync_cursors to service_role;
grant usage, select on all sequences in schema public to service_role;
