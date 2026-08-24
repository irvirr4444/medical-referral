alter table public.referral_reviews
    add column if not exists review_purpose text not null default 'destination_write',
    add column if not exists workflow_case_id text;

alter table public.referral_reviews
    drop constraint if exists referral_reviews_review_purpose_check;

alter table public.referral_reviews
    add constraint referral_reviews_review_purpose_check
    check (review_purpose in ('destination_write', 'partner_contact'));

alter table public.referral_reviews
    drop constraint if exists referral_reviews_status_check;

alter table public.referral_reviews
    add constraint referral_reviews_status_check
    check (
        status in (
            'awaiting_confirmation',
            'needs_correction',
            'confirmed',
            'partner_contact_confirmed',
            'dry_run_completed',
            'review_send_failed',
            'applying_monday',
            'monday_applied_drk_pending',
            'failed'
        )
    );

create index if not exists referral_reviews_workflow_case_lookup
    on public.referral_reviews (workflow_case_id, review_purpose, created_at desc)
    where workflow_case_id is not null;

drop index if exists public.referral_reviews_active_unique;
create unique index referral_reviews_active_unique
    on public.referral_reviews (
        artifact_digest,
        source_message_id,
        recipient,
        review_purpose
    )
    where status in (
        'awaiting_confirmation',
        'needs_correction',
        'review_send_failed'
    );

create or replace function public.process_review_response(
    p_review_id text,
    p_outlook_message_id text,
    p_sender text,
    p_conversation_id text,
    p_received_at timestamptz,
    p_intent text,
    p_classifier_source text,
    p_classifier_reason text,
    p_body_sha256 text
)
returns text
language plpgsql
set search_path = ''
as $$
declare
    current_status text;
    current_purpose text;
    confirmed_status text;
begin
    if exists (
        select 1 from public.review_responses
        where outlook_message_id = p_outlook_message_id
    ) then
        return 'duplicate';
    end if;

    select status, review_purpose
    into current_status, current_purpose
    from public.referral_reviews
    where review_id = p_review_id
      and recipient = lower(p_sender)
      and source_conversation_id = p_conversation_id
    for update;

    if not found then
        return 'no_matching_review';
    end if;
    if current_status <> 'awaiting_confirmation' then
        return 'review_state_changed';
    end if;

    insert into public.review_responses (
        review_id, outlook_message_id, sender, conversation_id, received_at,
        intent, classifier_source, classifier_reason, body_sha256
    ) values (
        p_review_id, p_outlook_message_id, lower(p_sender), p_conversation_id,
        p_received_at, p_intent, p_classifier_source, p_classifier_reason,
        p_body_sha256
    );

    if p_intent = 'confirm' then
        confirmed_status := case
            when current_purpose = 'partner_contact' then 'partner_contact_confirmed'
            else 'confirmed'
        end;
        update public.referral_reviews
        set status = confirmed_status,
            confirmed_at = now(),
            confirmation_message_id = p_outlook_message_id,
            error = null
        where review_id = p_review_id;
        return confirmed_status;
    elsif p_intent = 'correction' then
        update public.referral_reviews
        set status = 'needs_correction',
            confirmation_message_id = p_outlook_message_id,
            error = null
        where review_id = p_review_id;
        return 'needs_correction';
    end if;

    return 'unclear';
exception
    when unique_violation then
        return 'duplicate';
end;
$$;

revoke all on function public.process_review_response(
    text, text, text, text, timestamptz, text, text, text, text
) from public, anon, authenticated;

grant execute on function public.process_review_response(
    text, text, text, text, timestamptz, text, text, text, text
) to service_role;

create or replace function public.claim_review_for_monday_execution(p_review_id text)
returns text
language plpgsql
set search_path = ''
as $$
declare
    current_status text;
    current_purpose text;
begin
    select status, review_purpose
    into current_status, current_purpose
    from public.referral_reviews
    where review_id = p_review_id
    for update;

    if not found then
        return 'missing';
    end if;
    if current_purpose <> 'destination_write' then
        return 'wrong_purpose';
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
    set status = 'applying_monday', error = null
    where review_id = p_review_id
      and review_purpose = 'destination_write'
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
