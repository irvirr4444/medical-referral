# Outlook referral intake

This folder owns the email-facing adapters. It reads PDF attachments from either a
live Outlook inbox through Microsoft Graph or saved `.eml` fixtures and hands the
accepted attachments to `referral_pipeline`.

It can send review requests and read replies, but it does not delete, move, or
mark email as read. Destination writes remain owned by `referral_pipeline`.

## Folder contents

- `graph.py`: Microsoft Graph authentication and small HTTP primitives.
- `mail.py`: shared PDF validation, `.eml` parsing, attachment hashing, and local materialization.
- `review_mail.py`: HTML review replies on the source thread and unique reply-body retrieval.
- `README.md`: Outlook/Entra configuration and adapter behavior.

Cross-system orchestration and idempotency live in `src/referral_pipeline`. Monday
lookups and writes remain in `src/monday.com`.

## Configuration

Create an Entra application with Microsoft Graph `Mail.Read` and `Mail.Send`
application permissions, grant tenant admin consent, and scope it to the intended
mailbox when possible. Put these values in the repository-root `.env` file:

```dotenv
OUTLOOK_TENANT_ID=
OUTLOOK_CLIENT_ID=
OUTLOOK_CLIENT_SECRET=
OUTLOOK_MAILBOX=
REVIEW_RECIPIENT_EMAIL=
```

The mailbox adapter accepts an attachment only when its filename ends in `.pdf`
and its bytes begin with a PDF signature. Keep `.env`, downloaded PDFs, SQLite
state, and run artifacts out of Git because they can contain credentials or PHI.
Inbox messages are eligible only when Sent Items does not contain a message in
the same Outlook conversation. This prevents the automation from examining and
replying to a thread the mailbox has already answered.

Review replies are sent as Outlook-compatible HTML with a plain-text audit copy.
Formatting is deterministic from the canonical extraction: missing fields say
`Not documented`, and explicit NKA/NKDA is shown as `No known allergies`.

## Normal operation

Extract unreplied referral PDFs and reply on each Outlook thread with the review
summary, addressed to the configured reviewer, without changing Monday:

```powershell
python run_pipeline.py outlook --send-review --max-messages 25
```

`--max-messages` counts eligible unreplied referral emails (newest first). The
adapter pages beyond the newest raw inbox rows so replied threads do not hide
older unreplied PDFs.

If Anthropic is overloaded, the job is stored as `pending_retry` and can be
drained later without re-polling the whole mailbox:

```powershell
python run_pipeline.py retries
```

Inspect permanent failures (CLI report only; no alert email) and requeue one:

```powershell
python run_pipeline.py failures
python run_pipeline.py failures --requeue <sha256>
```

After the authorized reviewer replies with the exact command shown in the email,
poll replies and apply the approved Monday payload:

```powershell
python run_pipeline.py approvals --execute
```

If review delivery fails after extraction, resend from that run without repeating
the LLM calls:

```powershell
python run_pipeline.py review-send --run tmp/inbox-runs/20260804-120000
```

The older manual smoke-test path remains available for diagnostics:

```powershell
python run_pipeline.py outlook --apply --confirm-master-sheet-write
```

The CLI defaults to 25 eligible unreplied messages, uses the canonical Anthropic
Files API extractor, performs optional Monday duplicate and agency lookups,
stores timestamped audit artifacts under `tmp/inbox-runs/`, and prints progress.
The approval command writes Monday first and then records a DRK handoff. DRK
automatic patient creation is still disabled. Run the following for all options:

```powershell
python run_pipeline.py outlook --help
```

## Local `.eml` and debugging

Synthetic or saved email fixtures can use the lower-level runner without Outlook
credentials:

```powershell
python src/referral_pipeline/runner.py `
  --eml tmp/synthetic-referrals/emails/synthetic-complete.eml `
  --monday-mode snapshot `
  --monday-records-file tmp/synthetic-referrals/monday-snapshots/master_sheet_records.json `
  --agency-mode snapshot `
  --agency-records-file tmp/synthetic-referrals/monday-snapshots/accounts_records.json `
  --output-dir tmp/synthetic-inbox-run `
  --verbose
```

The lower-level runner is intended for fixture replay, batch processing, and
diagnostics. Normal operators should use `intake.py`.

## Tests

From the repository root:

```powershell
$env:PYTHONPATH = 'src'
python -m pytest tests/test_outlook tests/test_referral_pipeline src/monday.com/tests/test_synthetic_referrals.py -q
```
