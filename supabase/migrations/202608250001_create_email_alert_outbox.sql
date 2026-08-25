-- Durable product-email delivery, separate from exception/health digests.

create table if not exists public.wcw_email_alert_outbox (
    alert_key text primary key,
    action_id text not null,
    patient_id text not null,
    subject text not null,
    body_text text not null,
    body_html text not null,
    to_roles jsonb not null default '[]'::jsonb,
    cc_roles jsonb not null default '[]'::jsonb,
    case_emails jsonb not null default '{}'::jsonb,
    status text not null default 'pending'
        check (status in ('pending', 'sent', 'failed')),
    attempts integer not null default 0 check (attempts >= 0),
    last_error text,
    created_at timestamptz not null
);

create index if not exists idx_wcw_email_alert_outbox_pending
    on public.wcw_email_alert_outbox (status, created_at);

alter table public.wcw_email_alert_outbox enable row level security;
revoke all on public.wcw_email_alert_outbox from anon, authenticated;
grant all on public.wcw_email_alert_outbox to service_role;
