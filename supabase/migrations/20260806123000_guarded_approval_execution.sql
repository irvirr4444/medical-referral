-- Guarded approval execution: dry-run audit + atomic Monday claim.

alter table public.referral_reviews
    drop constraint if exists referral_reviews_status_check;

alter table public.referral_reviews
    add constraint referral_reviews_status_check
    check (
        status in (
            'awaiting_confirmation',
            'needs_correction',
            'confirmed',
            'dry_run_completed',
            'applying_monday',
            'monday_applied_drk_pending',
            'review_send_failed',
            'failed'
        )
    );

alter table public.referral_reviews
    add column if not exists last_dry_run_at timestamptz;

alter table public.referral_reviews
    add column if not exists last_dry_run_result jsonb;

create or replace function public.claim_review_for_monday_execution(p_review_id text)
returns text
language plpgsql
set search_path = ''
as $$
declare
    current_status text;
begin
    select status
    into current_status
    from public.referral_reviews
    where review_id = p_review_id
    for update;

    if not found then
        return 'missing';
    end if;

    if current_status = 'applying_monday' then
        return 'already_claiming';
    end if;

    if current_status = 'monday_applied_drk_pending' then
        return 'already_applied';
    end if;

    if current_status not in ('confirmed', 'dry_run_completed') then
        return 'not_confirmed';
    end if;

    update public.referral_reviews
    set status = 'applying_monday',
        error = null
    where review_id = p_review_id
      and status in ('confirmed', 'dry_run_completed');

    if not found then
        return 'race_lost';
    end if;

    return 'claimed';
end;
$$;

revoke all on function public.claim_review_for_monday_execution(text)
    from public, anon, authenticated;

grant execute on function public.claim_review_for_monday_execution(text)
    to service_role;
