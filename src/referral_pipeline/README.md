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
Review reply on source thread and sender-bound confirmation
        |
        v
Monday create, then audited DRK handoff
```

The normal operator entry point is the repository-root `run_pipeline.py`. Intake
does not write to Monday; an exact reply from the configured reviewer authorizes
the immutable artifact bundle. Capacity failures are queued as `pending_retry`
instead of failing permanently.

## Commands

Process unreplied Outlook PDF referrals, build destination drafts, and reply on
the source message's thread to the configured reviewer:

```powershell
python run_pipeline.py outlook --send-review
```

`--max-messages` defaults to 25 and counts **eligible unreplied referral emails**
(newest first). The Outlook adapter pages through the inbox so older unreplied
referrals are not hidden behind newer replied mail.

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
`INTAKE_DATA_ROOT=/var/data/intake`. The worker alternates Outlook discovery and
retry drains on configurable intervals while surviving cycle-level errors.

Local one-shot commands (`outlook`, `retries`, `failures`, `approvals`) remain
available for testing on any machine.

After the reviewer replies with the command printed in that email:

```powershell
python run_pipeline.py approvals --execute
```

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
- Review replies reuse one active review token/body for the same artifact digest

Validate fallback quality against the synthetic/golden referral set before relying
on it in production.

## Responsibilities

- `cli.py`: operator commands, safe defaults, latest-run pointer, retries, failures, and guarded apply.
- `runner.py`: source polling, PDF materialization, durable queue claims, and batch execution.
- `worker.py`: continuous Render-friendly poll + retry loop over durable disk paths.
- `service.py`: one accepted PDF through canonical Files API extraction, destination projections, planning, Monday preview, and optional create.
- `state.py`: SQLite job ledger, lease recovery, retry scheduling, permanent-failure retention, and Anthropic circuit breaker.
- `review/`: deterministic HTML/plain-text summary rendering, token/sender gating, durable review state, and destination execution.

Review emails are Outlook-compatible HTML plus a plain-text audit file
(`review-email.html` and `review-email.txt`). Sections include Needs attention,
Patient, Insurance, Diagnoses, Medications, Allergies, Clinical summary,
and Review decision. The decision explains how to confirm the Monday create and
DRK handoff, or how to reply with field corrections. Detailed extraction notes
and warnings stay in
`canonical-referral.json`; they are not repeated in the email. Missing values
use `Not documented`; explicit NKA/NKDA uses `No known allergies`. Formatting
never reinterprets the PDF or invents medical facts.

The read-only Monday duplicate gate compares normalized patient name, DOB,
phone, and address. When all four match, Needs attention identifies the
duplicate and lists those four Monday values; when no duplicate is found, the
email says nothing about duplicates. It is disabled by default for test runs.
Set `MONDAY_DUPLICATE_CHECK_ENABLED = True` in `referral_pipeline/cli.py` to
enable it globally, or use `--monday-mode live-readonly` for one run.

Every production intake writes `canonical-referral.json`, `inbox-intake.txt`, and
`drk-create-draft.json` from the same immutable extraction. Compatibility modules
may project that record into older schemas, but must not interpret the PDF again.

The Outlook and Monday folders contain adapters, not workflow ownership. A confirmed
review can create the Monday item and emits `drk-handoff.json` afterward. DRK's
duplicate check and form-filling tools remain separate, and automatic **Create
Patient** submission is intentionally unimplemented.
