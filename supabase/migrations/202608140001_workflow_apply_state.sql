-- Durable apply state for partner-contact confirmations. Receiving an Outlook
-- reply and advancing Stage 1 -> Stage 2 are separate writes.

alter table public.referral_reviews
    add column if not exists workflow_apply_status text;

alter table public.referral_reviews
    add column if not exists workflow_apply_attempts integer not null default 0;

alter table public.referral_reviews
    add column if not exists workflow_apply_last_error text;

alter table public.referral_reviews
    drop constraint if exists referral_reviews_workflow_apply_status_check;

alter table public.referral_reviews
    add constraint referral_reviews_workflow_apply_status_check
    check (
        workflow_apply_status is null
        or workflow_apply_status in ('pending', 'applied', 'failed', 'not_required')
    );

alter table public.referral_reviews
    drop constraint if exists referral_reviews_workflow_apply_attempts_check;

alter table public.referral_reviews
    add constraint referral_reviews_workflow_apply_attempts_check
    check (workflow_apply_attempts >= 0);

create index if not exists referral_reviews_workflow_apply_pending
    on public.referral_reviews (workflow_apply_status, created_at)
    where review_purpose = 'partner_contact'
      and status = 'partner_contact_confirmed'
      and coalesce(workflow_apply_status, 'pending') in ('pending', 'failed');

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
    apply_status text;
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
        apply_status := case
            when current_purpose = 'partner_contact' then 'pending'
            else 'not_required'
        end;
        update public.referral_reviews
        set status = confirmed_status,
            confirmed_at = now(),
            confirmation_message_id = p_outlook_message_id,
            error = null,
            workflow_apply_status = coalesce(workflow_apply_status, apply_status)
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
