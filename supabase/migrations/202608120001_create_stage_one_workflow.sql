-- Minimal durable Stage 1 coordination. Detailed Monday and DRK records remain
-- in their source systems; this schema stores workflow state and audit events.

create table if not exists public.wcw_workflow_cases (
    case_id text primary key,
    source_ref text not null unique,
    source text not null check (source in ('outlook-graph', 'eml-fixture')),
    attachment_sha256 text
        check (attachment_sha256 is null or attachment_sha256 ~ '^[a-f0-9]{64}$'),
    referral_id text,
    patient_label text,
    current_stage smallint not null default 1 check (current_stage between 1 and 7),
    status text not null
        check (status in ('discovered', 'processing', 'needs_attention', 'completed', 'failed')),
    source_received_at timestamptz,
    monday_item_id text unique,
    drk_patient_id text unique,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    completed_at timestamptz,
    check (completed_at is null or completed_at >= created_at)
);

create index if not exists idx_wcw_workflow_cases_updated
    on public.wcw_workflow_cases (updated_at desc);

create index if not exists idx_wcw_workflow_cases_attachment_sha256
    on public.wcw_workflow_cases (attachment_sha256)
    where attachment_sha256 is not null;

create index if not exists idx_wcw_workflow_cases_referral_id
    on public.wcw_workflow_cases (referral_id)
    where referral_id is not null;

create table if not exists public.wcw_outbound_acknowledgements (
    case_id text primary key references public.wcw_workflow_cases(case_id) on delete cascade,
    recipient text not null check (length(trim(recipient)) > 3),
    payload_digest text not null check (payload_digest ~ '^[a-f0-9]{64}$'),
    status text not null default 'pending'
        check (status in ('pending', 'sending', 'sent', 'failed')),
    attempts integer not null default 0 check (attempts >= 0),
    lease_until timestamptz,
    sent_at timestamptz,
    last_error text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    check (sent_at is null or sent_at >= created_at)
);

create index if not exists idx_wcw_workflow_events_timeline
    on public.wcw_workflow_events (entity_id, occurred_at desc);

alter table public.wcw_workflow_cases enable row level security;
alter table public.wcw_outbound_acknowledgements enable row level security;

revoke all on public.wcw_workflow_cases from anon, authenticated;
revoke all on public.wcw_outbound_acknowledgements from anon, authenticated;

grant select, insert, update, delete on public.wcw_workflow_cases to service_role;
grant select, insert, update, delete on public.wcw_outbound_acknowledgements to service_role;

create or replace function public.claim_wcw_acknowledgement(
    p_case_id text,
    p_recipient text,
    p_payload_digest text,
    p_lease_seconds integer default 300
)
returns text
language plpgsql
set search_path = ''
as $$
declare
    current_row public.wcw_outbound_acknowledgements%rowtype;
    now_at timestamptz := clock_timestamp();
begin
    if p_case_id is null or p_recipient is null or p_payload_digest !~ '^[a-f0-9]{64}$' then
        return 'invalid';
    end if;

    insert into public.wcw_outbound_acknowledgements (
        case_id, recipient, payload_digest, status, attempts, lease_until, created_at, updated_at
    ) values (
        p_case_id, lower(trim(p_recipient)), p_payload_digest, 'pending', 0, null, now_at, now_at
    ) on conflict (case_id) do nothing;

    select * into current_row
    from public.wcw_outbound_acknowledgements
    where case_id = p_case_id
    for update;

    if current_row.status = 'sent' then
        return 'already_sent';
    end if;
    if current_row.status = 'sending' and current_row.lease_until > now_at then
        return 'busy';
    end if;

    update public.wcw_outbound_acknowledgements
    set recipient = lower(trim(p_recipient)),
        payload_digest = p_payload_digest,
        status = 'sending',
        attempts = attempts + 1,
        lease_until = now_at + make_interval(secs => greatest(p_lease_seconds, 30)),
        last_error = null,
        updated_at = now_at
    where case_id = p_case_id;
    return 'claimed';
end;
$$;

revoke all on function public.claim_wcw_acknowledgement(text, text, text, integer)
    from public, anon, authenticated;
grant execute on function public.claim_wcw_acknowledgement(text, text, text, integer)
    to service_role;
