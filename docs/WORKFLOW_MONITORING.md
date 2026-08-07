# WCW Workflow Monitoring

This module adds durable operational state to the existing intake pipeline and
implements the parts of workflow Steps 4 and 5 that can be verified from recorded
Monday and DRK values. It does not schedule patients, discharge patients, infer a
clinical outcome, or write status changes back to either system.

## What it records

- `wcw_patient_links`: the internal referral ID and its known Monday/DRK IDs.
- `wcw_system_snapshots`: changed normalized source states, not repeated copies of unchanged rows.
- `wcw_workflow_events`: intake, review, scheduling, visit, hold, healed, expired, and discharge observations.
- `wcw_workflow_exceptions`: open/resolved items that require a human decision.
- `wcw_notification_outbox`: deduplicated alerts waiting to be sent.
- `wcw_workflow_counters`: consecutive explicit `Not Seen` counts.
- `wcw_sync_cursors`: the last successful source observation time.
- `wcw_component_health`: PHI-free latest worker-cycle health and failure count.

Steps 1-3 also write lifecycle events when `WORKFLOW_DATABASE_BACKEND` is set:
preview ready/needs attention, review requested, review confirmed, Monday item
created, and DRK handoff created. Database failure is logged but does not corrupt
or repeat the primary intake operation.

## Supabase setup

1. Apply `supabase/migrations/202608060001_create_workflow_monitoring.sql` and
   `supabase/migrations/202608070001_create_component_health.sql` through the
   Supabase migration workflow or SQL editor.
2. Put `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` in local/server environment
   configuration, never in source control or browser code.
3. Set `WORKFLOW_DATABASE_BACKEND=supabase`.
4. Keep the created tables backend-only. The migration enables RLS and removes
   `anon` and `authenticated` access.

SQLite remains available for local testing:

```powershell
python run_pipeline.py monitor --monday-snapshot path\to\master-sheet-records.json --database-backend sqlite --sqlite-path tmp\monitor-test.sqlite
python run_pipeline.py monitor-status --database-backend sqlite --sqlite-path tmp\monitor-test.sqlite
```

Run against Monday without writing to it:

```powershell
python run_pipeline.py monitor --live-monday --database-backend supabase
```

This stores exceptions in the outbox but sends no email. Add `--send-alerts` only
after `WORKFLOW_NOTIFICATION_RECIPIENTS` and Outlook Mail.Send are verified.

## Step 4: scheduling

The monitor considers an active, case-manager-sent referral scheduled only when
all configured signals agree: Scheduled Status is `Scheduled`, Scheduling Complete
is `Yes`, and Appointment Date is present. At the configured end-of-day cutoff, a
due referral with no scheduling evidence creates one deduplicated exception.
Partial or conflicting evidence is classified as indeterminate and also requires
review. A later complete state resolves the open scheduling exception.

Business controls are environment-configurable:

```dotenv
WCW_TIMEZONE=America/Los_Angeles
WCW_END_OF_DAY=17:00
WORKFLOW_NOTIFICATION_RECIPIENTS=reviewer@example.com
```

## Step 5: visits

The first snapshot is a baseline. Later snapshots create events only from explicit
recorded transitions such as `Seen`, `Not Seen`, hold, return from hold, healed,
expired, or discharged. `Seen` resets the counter. Three consecutive `Not Seen`
records create a discharge-review exception, but the system never discharges the
patient automatically. Healed and expired records also create human-review items.
Repeated identical outcomes count as separate visits only when DRK supplies a new
`visit_event_id`, `visit_id`, `appointment_id`, or `visit_date`; polling the same
status repeatedly never inflates the counter.

## DRK read sources

Until a stable read-only DRK adapter is available, the monitor accepts normalized
JSON. It can be a list or `{ "patients": [...] }`:

```json
{
  "patients": [
    {
      "patient_id": "drk-123",
      "referral_id": "ref_abc123",
      "patient_label": "Example Patient",
      "appointment_date": "2026-08-10",
      "visit_status": "Seen",
      "visit_outcome": "Seen",
      "visit_event_id": "visit-456",
      "progress_note_status": "Signed",
      "updated_at": "2026-08-10T18:00:00Z"
    }
  ]
}
```

Run both sources together:

```powershell
python run_pipeline.py monitor --live-monday --drk-snapshot path\to\drk-status.json --database-backend supabase
```

The monitor can also normalize card directories produced by the existing
Selenium `drk_emr.read_patient` command:

```powershell
python run_pipeline.py monitor --live-monday --drk-capture-dir output\drk-browser-profile --database-backend supabase
```

The adapter reads exact keys configured in
`src/referral_pipeline/monitoring/drk_capture_profile.example.json`. It records
which card and JSON path supplied every normalized value and lists unavailable
monitoring fields. It never derives a patient ID from a folder name or treats a
generic DRK status as a visit outcome. Extend the profile only after observing
and verifying the corresponding DRK field. Selenium capture remains a separate
authorized read step in this replay mode.

For continuous operation, a separate production reader lives under
`src/drk_emr/live_reader`. It does not alter or import the legacy debugging CLI.
It logs in once per bounded batch, navigates directly by verified numeric DRK
patient ID, captures only supported same-host JSON responses, normalizes them in
memory, and closes the browser at the end of the cycle. Raw card files are not
written by this path.

```powershell
python run_pipeline.py monitor --live-monday --live-drk --drk-max-patients 10 --database-backend supabase
```

Only database links containing both a Monday item ID and a DRK patient ID are
eligible. Inactive Monday groups/statuses are excluded. A durable round-robin
cursor bounds each cycle and prevents the first patients from being reread
forever. If there are no linked eligible patients, the cycle succeeds with zero
attempts rather than searching DRK by name.

## Continuous operation

Monitoring is disabled by default in the worker. Enable it deliberately:

```dotenv
INTAKE_MONITOR_ENABLED=true
INTAKE_MONITOR_INTERVAL_SECONDS=3600
INTAKE_MONITOR_SEND_ALERTS=false
INTAKE_LIVE_DRK_ENABLED=false
INTAKE_DRK_MAX_PATIENTS_PER_CYCLE=10
```

Enable live DRK only on a single Chrome-capable worker after `EMR_URL`,
`EMR_USERNAME`, and `EMR_PASSWORD` are configured. The current native Render
runtime does not itself guarantee a Chrome installation; use a Chrome-capable
container/VM or verify the runtime before changing the flag. The dedicated
browser profile contains authenticated session data and must stay on restricted
durable storage. Do not run multiple workers against the same profile directory.

Live DRK reports independent `drk_reader` health. A patient-level failure does
not discard successful snapshots from the same batch; repeated partial or total
failures degrade health and eventually queue an operational alert.

`tmp/monitoring/last-run.json` for manual runs, or the worker data root's
`monitoring/last-run.json`, provides a small machine-readable status surface for a
future read-only UI. The immediate operator view is `monitor-status` plus the
exception and notification tables.

Worker health is enabled by default and records `poll`, `retries`, `approvals`,
and `monitor` cycle outcomes without raw exception text or patient data. A
component is degraded after an initial failure and failed after three consecutive
failures by default. Failure/recovery notifications use the existing outbox and
remain unsent unless `INTAKE_HEALTH_SEND_ALERTS=true`.

```powershell
python run_pipeline.py health --database-backend supabase --stale-after-seconds 7200
```

The command returns a nonzero exit code when a component is failed or stale, so
it can later back a deployment health check. A dead process cannot update its own
heartbeat; an external scheduler or hosting monitor must call this command to
detect that case.

## Remaining business gates

- Confirm the exact WCW end-of-day cutoff and alert recipients.
- Confirm the authoritative meaning/labels for scheduled, seen, hold, healed,
  expired, and discharged.
- Verify DRK encounter/status field aliases and populate exact Monday-to-DRK patient links.
- Provision and validate Chrome on the authorized continuous-reader host.
- Confirm the routing schedule source. No provider-route assignment is inferred.
- Complete vendor security and BAA review before storing production PHI in a cloud database.
