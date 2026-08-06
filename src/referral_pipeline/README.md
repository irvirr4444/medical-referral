# Referral pipeline orchestration

This package connects the system-specific adapters into one intake workflow:

```text
Outlook or saved .eml
        |
        v
PDF validation and durable SQLite queue
        |
        v
Anthropic circuit + Opus 5 with audited Opus 4.8 fallback
        |
        v
Canonical two-pass extraction and schema validation
        |
        v
Monday duplicate and agency checks
        |
        v
Master Sheet preview
        |
        v
Review reply on source thread and sender/thread-bound confirmation
        |
        v
Monday/DRK confirmation dry run (destination writes disabled)
```

The normal operator entry point is the repository-root `run_pipeline.py`. Intake
does not write to Monday. The original sender can reply naturally (for example,
`Confirm`); authorization remains deterministically bound to that sender, the
Outlook conversation, a message newer than the review, and immutable JSON snapshots
stored in Supabase. OpenAI classifies only ambiguous wording and cannot authorize a different
sender or thread. Transient dependency failures are queued as `pending_retry`
instead of failing permanently.

Supabase `referral_reviews` correlates each Outlook thread with the canonical
referral, intake plan, Monday preview, and DRK draft JSON. `review_responses`
records one hashed, classified event per Outlook reply. The raw reply body remains
in Outlook; the confirmation transition and response insert happen atomically.
Both tables have RLS enabled and are accessed only with the backend service key.

## Commands

Process new Outlook PDF referrals, build destination drafts, and reply on each
source thread to the original sender:

```powershell
python run_pipeline.py outlook --send-review
```

`--max-messages` defaults to 25 and counts **eligible new referral emails**
(newest first). The Outlook adapter pages through the inbox while SQLite state
excludes attachments that are already known.

Process due durable retries without polling Outlook again (scheduler-friendly):

```powershell
python run_pipeline.py retries
```

List permanent failures, then deliberately requeue one after the cause is fixed:

```powershell
python run_pipeline.py failures
python run_pipeline.py failures --requeue <sha256>
```

## Render background worker

Production should use one Render **background worker** with a persistent disk,
not a Render cron job (cron containers cannot keep SQLite/PDF state).

```powershell
python run_worker.py
# or: PYTHONPATH=src python -m referral_pipeline.worker --once
```

[`render.yaml`](../../render.yaml) mounts durable storage at `/var/data` and sets
`INTAKE_DATA_ROOT=/var/data/intake`. The worker runs Outlook discovery, retry
drains, and approval polling on independent intervals while surviving cycle-level
errors. Scheduled workers check replies only by default. Set
`INTAKE_DRY_RUN_APPROVALS=true` to validate confirmed reviews without writes.
Workers never execute real Monday creates.

Local one-shot commands (`outlook`, `retries`, `failures`, `approvals`) remain
available for testing on any machine.

After the original sender replies naturally to confirm:

```powershell
python run_pipeline.py approvals
python run_pipeline.py approvals --dry-run
# Explicit real Monday create:
python run_pipeline.py approvals --execute
```

The default command only classifies replies. `--dry-run` validates the immutable
Supabase JSON, seven required fields, digest, Monday preview, and DRK draft while
performing zero writes. `--execute` atomically claims each confirmed review and
creates its Monday item once. DRK Create Patient submission remains intentionally
unfinished and is recorded as `pending_draft`.

The manual exact-preview path remains available for debugging:

```powershell
python run_pipeline.py apply --confirm-master-sheet-write
```

Use `python run_pipeline.py outlook --help` for optional source, extraction,
lookup, output, and debugging flags.

## Reliability

- Primary model: `ANTHROPIC_PDF_MODEL` (default `claude-opus-5`)
- Fallback chain: `ANTHROPIC_PDF_FALLBACK_MODELS` (default `claude-opus-4-8`)
- Job states: `discovered`, `processing`, `pending_retry`, `completed`, `failed`
- Anthropic circuit: opens after repeated capacity failures, allows one half-open probe after cooldown
- Successful extraction artifacts record the model used under `source.extraction`
- Review replies reuse one active review/body for the same artifact digest
- Supabase stores durable review JSON snapshots and idempotent response correlation

Validate fallback quality against the synthetic/golden referral set before relying
on it in production.

## Responsibilities

- `cli.py`: operator commands, safe defaults, latest-run pointer, retries, failures, and guarded apply.
- `runner.py`: source polling, PDF materialization, durable queue claims, and batch execution.
- `retry_policy.py`: shared transient/permanent classification for Anthropic, Outlook, Monday, and network failures.
- `worker.py`: continuous Render-friendly discovery, retry, and approval loop over durable disk paths.
- `service.py`: one accepted PDF through canonical Files API extraction, destination projections, planning, Monday preview, and optional create.
- `state.py`: SQLite job ledger, lease recovery, retry scheduling, permanent-failure retention, and Anthropic circuit breaker.
- `review/`: Supabase persistence, deterministic HTML/plain-text summaries, natural-language intent classification, sender/thread/time gating, and dry-run confirmation.

Review emails are Outlook-compatible HTML plus a plain-text audit file
(`review-email.html` and `review-email.txt`). Sections include Needs attention,
Patient, Insurance, Diagnoses, Medications, Allergies, Clinical summary,
and Review decision. The decision explains how to reply naturally to confirm the
Monday/DRK dry run, or how to reply with field corrections. Detailed extraction notes
and warnings stay in
`canonical-referral.json`; they are not repeated in the email. Missing values
use `Not documented`; explicit NKA/NKDA uses `No known allergies`. Formatting
never reinterprets the PDF or invents medical facts.

The read-only Monday duplicate gate treats normalized patient name and DOB as a
candidate match. Phone and address remain supporting evidence and may match,
differ, or be missing; they do not hide the candidate. When no duplicate is
found, the email says nothing about duplicates. It is disabled by default for
manual test runs.
Set `MONDAY_DUPLICATE_CHECK_ENABLED = True` in `referral_pipeline/cli.py` to
enable it globally, or use `--monday-mode live-readonly` for one run.

Every production intake writes `canonical-referral.json`, `inbox-intake.txt`, and
`drk-create-draft.json` from the same immutable extraction. Compatibility modules
may project that record into older schemas, but must not interpret the PDF again.

The Outlook and Monday folders contain adapters, not workflow ownership. A confirmed
review can create the Monday item and emits `drk-handoff.json` afterward. DRK's
duplicate check and form-filling tools remain separate, and automatic **Create
Patient** submission is intentionally unimplemented.
