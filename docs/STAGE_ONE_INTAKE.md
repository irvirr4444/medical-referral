# Stage 1: Referral intake

Stage 1 turns one Outlook PDF attachment into one durable workflow case. It does
not create or update Monday or DRK records.

## Durable records

The implementation intentionally adds only two Stage 1-specific tables:

- `wcw_workflow_cases` is the cross-system case header. Later stages can attach
  Monday and DRK identifiers to the same case instead of creating another master
  table.
- `wcw_outbound_acknowledgements` is an idempotency gate for the one referral-
  partner acknowledgement.

The existing `wcw_workflow_events` table is the append-only timeline. It records
receipt, extraction, duplicate checks, acknowledgement delivery, and safe failure
codes. Detailed clinical records remain in the canonical extraction artifacts and
their destination systems.

The existing `referral_reviews` and `review_responses` tables carry the internal
summary email and its sender/thread-bound reply. Stage 1 records these requests with
`review_purpose = 'partner_contact'`; a confirmed reply completes microstep 5 and is
excluded from the destination-write approval queue.

All tables have row-level security enabled. Browser roles receive no table or RPC
access. Only the backend service-role key can use them. Never expose
`SUPABASE_SERVICE_ROLE_KEY` to the frontend.

## Apply the Supabase schema

Apply migrations in filename order. The Stage 1 migration depends on
`202608060001_create_workflow_monitoring.sql`, which creates the shared event table.

With a linked Supabase CLI project:

```powershell
supabase migration list
supabase db push --dry-run
supabase db push
```

Alternatively, run the relevant SQL files in filename order in the Supabase SQL editor,
including:

1. `supabase/migrations/202608060001_create_workflow_monitoring.sql`
2. `supabase/migrations/202608120001_create_stage_one_workflow.sql`
3. `supabase/migrations/202608120002_allow_duplicate_referral_ids.sql`
4. `supabase/migrations/202608120003_scope_review_confirmation.sql`
5. `supabase/migrations/202608130001_harden_stage_one_workflow.sql`

After applying them, set the backend environment only:

```dotenv
WORKFLOW_DATABASE_BACKEND=supabase
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...
SYNTHETIC_DATASET_MANIFEST=output/pdf/synthetic-referrals/dataset.json
```

Referral persistence is fail-closed while this project uses test data. A PDF may
enter Supabase only when its SHA-256 hash appears in a manifest marked
`synthetic_only: true`. Unknown PDFs, including the WCW samples under `samples/`,
continue through local processing but use SQLite for Stage 1 and review records.
The filename is never trusted as proof that a document is synthetic. If the
manifest is missing or invalid, no referral is eligible for remote persistence.

Use SQLite locally without any migration command:

```dotenv
WORKFLOW_DATABASE_BACKEND=sqlite
WORKFLOW_SQLITE_PATH=tmp/workflow-monitor.sqlite
```

## Controlled Stage 1 test

The complete test-inbox Stage 1 path is:

```powershell
python run_pipeline.py stage-one-doctor --live
python run_pipeline.py outlook --max-messages 1 --monday-mode live-readonly --drk-duplicate-check --send-partner-acknowledgement --send-review
```

This command:

1. Reads the newest eligible Outlook PDF.
2. Creates or reuses its durable case.
3. Runs the canonical Anthropic Files API extraction.
4. Checks Monday for a patient candidate without writing.
5. Checks DRK through the read-only Selenium duplicate gate without writing.
6. Sends the extracted summary to the configured internal reviewer.
7. Marks microstep 5 complete only after that reviewer reports `Confirmed`,
   `No answer`, or `Information missing` in the same Outlook thread. The normalized
   outcome is stored on the Stage 1 event for Stage 2 routing.
8. Exposes the persisted microsteps to the local intake API and frontend.

The acknowledgement and DRK check are explicit flags. Omitting them cannot send
the partner email or open the DRK browser. Monday and DRK writes remain disabled.
The detailed summary has no external fallback: `REVIEW_RECIPIENT_EMAIL` must be an
explicit internal intake-team address whenever `--send-review` is enabled.

Preview both outbound messages without sending or persisting anything:

```powershell
python run_pipeline.py stage-one-email-preview --run tmp\inbox-runs\<timestamp>
```

Run the frontend projection separately:

```powershell
python run_pipeline.py inbox-api
```

The local API binds only to `127.0.0.1` until authentication is implemented.
It remains available while the background monitor is OFF because the frontend
still reads the saved feed and monitor status. Terminal lines for
`GET /api/intake/inbox` and `GET /api/intake/monitor` are read-only UI polling,
not Outlook processing. Stop the worker from the UI; use `Ctrl+C` to stop the API
itself.

The DRK feed label follows the reported safety configuration. It shows `DRK chart
check disabled` only when `drk_duplicate_check` is explicitly false, remains
queued when the check is enabled or configuration is unavailable, and preserves
any completed DRK result already stored for the referral.

## Continuous worker

The same path can run continuously with these explicit worker settings:

```dotenv
INTAKE_PARTNER_ACKNOWLEDGEMENT_ENABLED=true
INTAKE_STAGE_ONE_DRK_CHECK_ENABLED=true
```

Leave both `false` until the test mailbox recipient and DRK account have been
approved. The worker stores its intake queue and workflow database under the same
durable `INTAKE_DATA_ROOT`.

## Delivery guarantee

Database claims prevent normal retries and concurrent workers from sending the
same acknowledgement twice. As with any external email API, there is a narrow
crash window after Microsoft accepts a message but before the database records
`sent`; exact-once delivery cannot be guaranteed across that external boundary.
The timeline and acknowledgement attempt count make this edge case auditable.
