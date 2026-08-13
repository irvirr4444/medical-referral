-- Align Stage 1 states and enforce relationships used by later workflow stages.

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
            'failed'
        )
    ) not valid;

alter table public.wcw_workflow_cases
    validate constraint wcw_workflow_cases_status_check;

do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conname = 'referral_reviews_workflow_case_fk'
          and conrelid = 'public.referral_reviews'::regclass
    ) then
        alter table public.referral_reviews
            add constraint referral_reviews_workflow_case_fk
            foreign key (workflow_case_id)
            references public.wcw_workflow_cases(case_id)
            on delete set null
            not valid;
    end if;
end
$$;

do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conname = 'wcw_notification_outbox_exception_fk'
          and conrelid = 'public.wcw_notification_outbox'::regclass
    ) then
        alter table public.wcw_notification_outbox
            add constraint wcw_notification_outbox_exception_fk
            foreign key (exception_key)
            references public.wcw_workflow_exceptions(exception_key)
            on delete restrict
            not valid;
    end if;
end
$$;

alter table public.wcw_notification_outbox
    drop constraint if exists wcw_notification_outbox_attempts_check;
alter table public.wcw_notification_outbox
    add constraint wcw_notification_outbox_attempts_check
    check (attempts >= 0) not valid;

alter table public.wcw_workflow_counters
    drop constraint if exists wcw_workflow_counters_value_check;
alter table public.wcw_workflow_counters
    add constraint wcw_workflow_counters_value_check
    check (value >= 0) not valid;

alter table public.wcw_outbound_acknowledgements
    drop constraint if exists wcw_outbound_acknowledgements_attempts_check;
alter table public.wcw_outbound_acknowledgements
    add constraint wcw_outbound_acknowledgements_attempts_check
    check (attempts >= 0) not valid;

alter table public.wcw_workflow_cases
    drop constraint if exists wcw_workflow_cases_timestamp_order_check;
alter table public.wcw_workflow_cases
    add constraint wcw_workflow_cases_timestamp_order_check
    check (
        updated_at >= created_at
        and (completed_at is null or completed_at >= created_at)
    ) not valid;

-- NOT VALID still protects new writes while allowing existing demo rows to be
-- audited before these historical constraints are validated explicitly.
