-- PHI-free latest health state for continuously running workflow components.

create table if not exists public.wcw_component_health (
    component text primary key,
    status text not null check (status in ('healthy', 'degraded', 'failed')),
    last_attempt_at timestamptz not null,
    last_success_at timestamptz,
    consecutive_failures integer not null default 0 check (consecutive_failures >= 0),
    duration_seconds double precision,
    error_code text
);

alter table public.wcw_component_health enable row level security;
revoke all on public.wcw_component_health from anon, authenticated;
grant all on public.wcw_component_health to service_role;
