# Continuous DRK Reader

This package is the read-only production companion to the legacy
`drk_emr.read_patient` debugging CLI. The two implementations are intentionally
separate.

The continuous reader:

- receives verified numeric DRK patient IDs from stored Monday/DRK links;
- opens one authenticated Selenium Wire browser for a bounded batch;
- navigates directly to each patient dashboard without a name search;
- captures only allowlisted same-host JSON card responses;
- normalizes card payloads in memory and does not persist raw card JSON;
- isolates patient-level failures and closes the browser after the batch.

It never schedules, edits, creates, or discharges a DRK patient.

## Manual live cycle

```powershell
python run_pipeline.py monitor --live-monday --live-drk --drk-max-patients 10 --database-backend supabase
```

## Continuous worker

```powershell
python run_worker.py --monitor --live-drk --drk-max-patients 10
```

Set `EMR_URL`, `EMR_USERNAME`, and `EMR_PASSWORD`. The host must provide Chrome.
Headless mode is enabled by default through `DRK_LIVE_HEADLESS=true`.

No patients are read until `wcw_patient_links` contains both their Monday item ID
and DRK patient ID. Selection excludes configured inactive Monday states and uses
a persistent round-robin cursor. Run only one worker against a browser profile.
