create extension if not exists pgcrypto;

create table if not exists public.referral_reviews (
    id uuid primary key default gen_random_uuid(),
    review_id text not null unique,
    recipient text not null,
    status text not null default 'awaiting_confirmation'
        check (
            status in (
                'awaiting_confirmation',
                'needs_correction',
                'confirmed',
                'dry_run_completed',
                'review_send_failed',
                'failed'
            )
        ),
    source_message_id text not null,
    source_conversation_id text not null,
    source_attachment_sha256 text,
    artifact_digest text not null
        check (artifact_digest ~ '^[a-f0-9]{64}$'),
    canonical_referral jsonb not null
        check (jsonb_typeof(canonical_referral) = 'object'),
    intake_plan jsonb not null
        check (jsonb_typeof(intake_plan) = 'object'),
    monday_preview jsonb not null
        check (jsonb_typeof(monday_preview) = 'object'),
    drk_draft jsonb not null
        check (jsonb_typeof(drk_draft) = 'object'),
    email_subject text,
    email_html_body text,
    email_text_body text,
    email_content_type text
        check (email_content_type in ('HTML', 'TEXT')),
    review_sent_at timestamptz,
    confirmed_at timestamptz,
    confirmation_message_id text unique,
    monday_item_id text,
    drk_status text,
    error text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.review_responses (
    id uuid primary key default gen_random_uuid(),
    review_id text not null references public.referral_reviews(review_id)
        on update cascade
        on delete cascade,
    outlook_message_id text not null unique,
    sender text not null,
    conversation_id text not null,
    received_at timestamptz not null,
    intent text not null
        check (intent in ('confirm', 'correction', 'unclear')),
    classifier_source text not null
        check (classifier_source in ('local', 'openai')),
    classifier_reason text,
    body_sha256 text not null
        check (body_sha256 ~ '^[a-f0-9]{64}$'),
    processed_at timestamptz not null default now(),
    created_at timestamptz not null default now()
);

create unique index if not exists referral_reviews_active_unique
    on public.referral_reviews (
        artifact_digest,
        source_message_id,
        recipient
    )
    where status in (
        'awaiting_confirmation',
        'needs_correction',
        'review_send_failed'
    );

create index if not exists referral_reviews_reply_lookup
    on public.referral_reviews (
        recipient,
        source_conversation_id,
        status,
        created_at desc
    );

create index if not exists review_responses_review_lookup
    on public.review_responses (review_id, processed_at desc);

create index if not exists review_responses_conversation_lookup
    on public.review_responses (conversation_id, received_at desc);

create or replace function public.set_referral_review_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists set_referral_review_updated_at on public.referral_reviews;
create trigger set_referral_review_updated_at
before update on public.referral_reviews
for each row
execute function public.set_referral_review_updated_at();

alter table public.referral_reviews enable row level security;
alter table public.review_responses enable row level security;

revoke all on public.referral_reviews from anon, authenticated;
revoke all on public.review_responses from anon, authenticated;

grant all on public.referral_reviews to service_role;
grant all on public.review_responses to service_role;

