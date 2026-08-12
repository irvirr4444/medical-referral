-- A workflow case represents one inbound attachment. The same referral may be
-- resent, so referral_id is searchable but must not identify the case.

alter table public.wcw_workflow_cases
    drop constraint if exists wcw_workflow_cases_referral_id_key;

create index if not exists idx_wcw_workflow_cases_referral_id
    on public.wcw_workflow_cases (referral_id)
    where referral_id is not null;
