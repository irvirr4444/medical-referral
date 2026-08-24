-- At-most-once Stage 3 execution. Preview must not consume an operation.
-- Expired running leases become uncertain and are never auto-retried.

alter table public.wcw_external_operations
    add column if not exists lease_until timestamptz;

alter table public.wcw_external_operations
    add column if not exists claimed_by text;

alter table public.wcw_external_operations
    drop constraint if exists wcw_external_operations_status_check;

alter table public.wcw_external_operations
    add constraint wcw_external_operations_status_check
    check (
        status in ('ready', 'running', 'succeeded', 'blocked', 'failed', 'uncertain')
    );

create index if not exists idx_wcw_external_operations_lease
    on public.wcw_external_operations (status, lease_until)
    where status = 'running';

create or replace function public.claim_wcw_external_operation(
    p_operation_id text,
    p_claimed_by text,
    p_lease_seconds integer default 300,
    p_allow_uncertain boolean default false
)
returns text
language plpgsql
set search_path = ''
as $$
declare
    current_row public.wcw_external_operations%rowtype;
    now_at timestamptz := clock_timestamp();
begin
    if p_operation_id is null or length(trim(p_operation_id)) = 0 then
        return 'not_found';
    end if;

    select * into current_row
    from public.wcw_external_operations
    where operation_id = p_operation_id
    for update;

    if not found then
        return 'not_found';
    end if;
    if current_row.status = 'succeeded' then
        return 'already_succeeded';
    end if;
    if current_row.status = 'running' and current_row.lease_until is not null
       and current_row.lease_until > now_at then
        return 'busy';
    end if;
    if current_row.status = 'running'
       and (current_row.lease_until is null or current_row.lease_until <= now_at) then
        update public.wcw_external_operations
        set status = 'uncertain',
            lease_until = null,
            last_error = 'running lease expired; external outcome is unknown',
            updated_at = now_at
        where operation_id = p_operation_id;
        return 'uncertain';
    end if;
    if current_row.status = 'uncertain' and not coalesce(p_allow_uncertain, false) then
        return 'uncertain';
    end if;
    if current_row.status not in ('ready', 'failed', 'blocked')
       and not (current_row.status = 'uncertain' and coalesce(p_allow_uncertain, false)) then
        return 'not_retryable';
    end if;

    update public.wcw_external_operations
    set status = 'running',
        attempts = attempts + 1,
        claimed_by = nullif(trim(p_claimed_by), ''),
        lease_until = now_at + make_interval(secs => greatest(coalesce(p_lease_seconds, 300), 30)),
        last_error = null,
        updated_at = now_at
    where operation_id = p_operation_id;
    return 'claimed';
end;
$$;

revoke all on function public.claim_wcw_external_operation(text, text, integer, boolean)
    from public, anon, authenticated;
grant execute on function public.claim_wcw_external_operation(text, text, integer, boolean)
    to service_role;
