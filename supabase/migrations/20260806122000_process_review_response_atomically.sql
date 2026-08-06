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
begin
    if exists (
        select 1
        from public.review_responses
        where outlook_message_id = p_outlook_message_id
    ) then
        return 'duplicate';
    end if;

    select status
    into current_status
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
        review_id,
        outlook_message_id,
        sender,
        conversation_id,
        received_at,
        intent,
        classifier_source,
        classifier_reason,
        body_sha256
    ) values (
        p_review_id,
        p_outlook_message_id,
        lower(p_sender),
        p_conversation_id,
        p_received_at,
        p_intent,
        p_classifier_source,
        p_classifier_reason,
        p_body_sha256
    );

    if p_intent = 'confirm' then
        update public.referral_reviews
        set status = 'confirmed',
            confirmed_at = now(),
            confirmation_message_id = p_outlook_message_id,
            error = null
        where review_id = p_review_id;
        return 'confirmed';
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

