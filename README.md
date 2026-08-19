## medical-referral

Pipeline to extract **one normalized JSON record per referral/intake PDF** (digital forms, scanned faxes, EHR printouts) using Claude.

### PHI / safety

These PDFs contain **PHI**.

- **Do not commit generated outputs**. The `out/` folder is gitignored.
- `llm_direct.py` **prints the extracted JSON to stdout by default** (this will include PHI).

### Project structure (current)

- `samples/`: 7 reference PDFs (fixtures)
- `src/intake_extractor/canonical_referral.py`: the only PDF interpreter and extraction command
- `src/intake_extractor/aligned_intake.py`: destination adapters for Monday and DRK
- `src/intake_extractor/monday_pdf.py`: compatibility projection; does not independently interpret PDFs
- `src/intake_extractor/drk_pdf.py`: DRK card projection; does not independently interpret PDFs
- `docs/PDF_TRANSPORT.md`: Files API primary policy, inline fallback, PHI lifecycle, and troubleshooting
- `src/monday.com/build_aligned_intake.py`: preview-first Monday/DRK handoff orchestrator
- `src/drk_emr/create_patient/schema.py`: typed, non-submitting DRK Patient Intake draft
- `src/intake_extractor/pdf_inputs.py`: input-mode selection (`auto`, `text`, `image`, `hybrid`)
- `src/intake_extractor/pdf_payloads.py`: PDF text extraction + Poppler image rendering
- `src/intake_extractor/postprocess.py`: deterministic normalization / cleanup
- `src/intake_extractor/repair.py`: gated repair / merge rules for weak fields
- `src/intake_extractor/review*.py`: optional second-pass reviewer + audit flow
- `src/monday.com/push_referral.py`: extract one PDF and upsert it into a Monday board item
- `src/monday.com/referral_board_config.py`: typed config loader for board/group/column mapping
- `src/monday.com/referral_board_config.example.json`: example mapping for the current demo board
- `tests/`: focused extractor, repair, reviewer, and evaluator tests
- `out/`: local outputs (gitignored)

### Requirements

- **Python 3.11+**
- **Poppler utilities**:
  - `pdffonts` (detect text layer)
  - `pdftoppm` (rasterize scanned PDFs to PNGs)
- **ANTHROPIC_API_KEY** in environment (or `.env`)

### Setup

Install Poppler:

- **Windows (winget)**:

```powershell
winget install --id oschwartz10612.Poppler --exact
```

- **macOS (Homebrew)**:

```bash
brew install poppler
```

- **Ubuntu/Debian**:

```bash
sudo apt-get update && sudo apt-get install -y poppler-utils
```

Install Python deps:

```bash
python3.11 -m pip install -r requirements.txt
```

Set your API key:

```bash
cp .env.example .env
# edit .env and set ANTHROPIC_API_KEY=...
```

### Canonical PDF extraction

There is one source of truth and one supported PDF extraction command:

```bash
PYTHONPATH=src python3.11 -m intake_extractor.canonical_referral \
  "samples/BUTLER, ALVA demo.pdf"
```

It uploads the PDF once through the Anthropic Files API, performs exactly two model calls (complete extraction,
then source verification), deletes the temporary upload, and writes `canonical-referral.json`,
`inbox-intake.txt`, `monday-referral.json`, and `drk-create-draft.json`. The canonical
record retains all readable demographics, source organizations, home-health/hospice facts, clinical lists,
insurances, requested services, warnings, and per-field states (`present`, `explicitly_none`, `missing`,
`unclear`). Monday, DRK, and inbox workflows only project from this record; they never reinterpret the PDF.

Optional environment overrides:

```dotenv
ANTHROPIC_PDF_MODEL=claude-opus-5
ANTHROPIC_PDF_FALLBACK_MODELS=claude-opus-4-8
ANTHROPIC_PDF_EFFORT=max
ANTHROPIC_PDF_MAX_TOKENS=32000
ANTHROPIC_PDF_TRANSPORT=files-api
```

Capacity failures retry with jitter, then advance through the configured fallback
chain. Successful artifacts record the model used under `source.extraction`.
Validate fallback quality against the synthetic/golden referral set before
production rollout.

Inline native-PDF transport remains an explicit fallback:

```bash
PYTHONPATH=src python3.11 -m intake_extractor.canonical_referral \
  "samples/BUTLER, ALVA demo.pdf" \
  --pdf-transport inline
```

### Aligned PDF → parallel Monday + DRK handoffs

The aligned flow derives two views from `CanonicalReferral`:

1. `master_sheet_referral` for the existing Monday Master Sheet planner/writer
2. `drk_create_draft` matching the discovered DRK Patient Intake fields

Both are derived independently from the same canonical extraction and retain one correlation ID and source
SHA-256; neither target becomes the source for the other. Missing fields stay `null`; DRK catalog-backed fields
(payer, facility, place of service, and similar typeaheads) remain blockers until an exact DRK catalog match is
approved. Clinical referring-provider data is preserved but is not silently treated as the DRK assigned provider.

Build both previews from a completed high-accuracy extraction:

```bash
PYTHONPATH=src python3.11 src/monday.com/build_aligned_intake.py \
  --canonical-json "output/canonical-referrals/ref_.../canonical-referral.json" \
  --source-pdf "samples/referral.pdf" \
  --sent-by "Intake Info Box" \
  --config src/monday.com/master_sheet_write_config.example.json
```

Or extract and build the previews in one command:

```bash
PYTHONPATH=src python3.11 src/monday.com/build_aligned_intake.py \
  --pdf "samples/referral.pdf"
```

The default writes local PHI artifacts with mode `0600` and does not call Monday or DRK:

- `aligned-intake.json`
- `intake-plan.json`
- `master-sheet-preview.json`
- `drk-create-draft.json`
- `handoff-state.json`

Monday creation requires both `--apply-master-sheet` and `--confirm-master-sheet-write`. The current DRK
automation remains fill-only and never clicks **Create Patient**, so the orchestrator records a DRK draft and
blockers but does not claim that a DRK patient was created.

### Monday.com API (optional)

Monday’s API is **GraphQL** over HTTPS. Put your key in `.env` as `MONDAY_DOT_COM_API_KEY` (see `.env.example`).

Full endpoint cookbook + test runbook: [`src/monday.com/readme.md`](src/monday.com/readme.md)

Smoke test:

```bash
PYTHONPATH=src python3.11 src/monday.com/monday_client.py --pretty
```

Unit + live smoke tests (live tests gated by env flags):

```bash
PYTHONPATH=src pytest -q src/monday.com/tests -k unit
MONDAY_LIVE_TEST=1 PYTHONPATH=src pytest -q src/monday.com/tests -k live_readonly
```

Referral push smoke test (extract locally, print the would-be Monday payload, do not write to Monday):

```bash
PYTHONPATH=src python3.11 src/monday.com/push_referral.py \
  "samples/EC - REFERRAL FORM.pdf" \
  --config src/monday.com/referral_board_config.example.json \
  --input-mode image \
  --write-out-dir out/monday-smoke \
  --dry-run
```

### Live testing-infobox feed

From an activated virtual environment, the normal local development/demo startup is:

```powershell
& .\.venv\Scripts\Activate.ps1
python run_pipeline.py start
```

That command reuses a stable `INTAKE_DATA_ROOT` (or `tmp/intake-service` if unset),
runs the relevant preflight checks, starts the inbox API with autonomous monitoring,
starts the Vite frontend, waits until both are ready, and opens
`http://127.0.0.1:5173/`. Stop with Ctrl+C. Advanced controls remain under
`python run_pipeline.py start --help` and `python run_pipeline.py inbox-api --help`.

Vite proxies `/api` to `http://127.0.0.1:8787`. On **Referral intake**, the live
status indicator reports autonomous Outlook polling, extraction, safe duplicate
reads, durable retries, review-email delivery, and reply polling. Worker controls
are intentionally CLI-only; operators cannot start or stop infrastructure from the
workflow UI.

#### Manual debugging

Use separate terminals only when you need to debug the API or frontend in isolation.
Keep one stable `INTAKE_DATA_ROOT` so every run shares the same processed-attachment
ledger:

```powershell
$env:PYTHONPATH='src'
$env:INTAKE_DATA_ROOT='tmp/intake-service'
python run_pipeline.py inbox-api --start-monitor

cd frontend
npm run dev
```

The service starts OFF unless `--start-monitor` is supplied:

```powershell
python run_pipeline.py inbox-api --start-monitor
```

`inbox-api` remains running even when live monitoring is OFF. The frontend continues
making read-only `GET /api/intake/inbox` and `GET /api/intake/monitor` requests so it
can display saved referrals and worker status; those requests do not poll Outlook,
run extraction, send email, or write to Monday or DRK. Press `Ctrl+C` in the API
terminal to stop the service and its background worker.

The durable ledger is `<INTAKE_DATA_ROOT>/state.sqlite`. Completed, queued, and
permanently failed attachments are excluded from later polling. Do not rotate the
data root, delete this file, or pass `--force` during normal operation. The
`inbox-api` and one-off `outlook` commands now derive their defaults from the same
`INTAKE_DATA_ROOT`; an explicit `--state-db` remains available for debugging only.

The local service cannot write Monday or DRK. Partner acknowledgement and the DRK
duplicate check remain disabled unless their explicit CLI flags or environment
toggles are enabled. `REVIEW_RECIPIENT_EMAIL` is required before the monitor can
start, preventing review summaries from falling back to the referral sender.
Microsoft credentials and PDF bytes stay server-side. If the
API or Graph is unavailable, the frontend reports that state and keeps demo data.
For a referral without a persisted DRK result, the feed says **DRK chart check
disabled** only when the service explicitly reports that check OFF. It says
**Queued for DRK chart check** when enabled or when configuration is temporarily
unavailable; persisted DRK results always take priority.

### Workflow store: sqlite vs. Supabase

Stage 1-3 case state (`wcw_workflow_cases`, `wcw_work_items`, decisions, external
operations) lives in `WORKFLOW_DATABASE_BACKEND`, either `sqlite` (default, path
`WORKFLOW_SQLITE_PATH` or `<INTAKE_DATA_ROOT>/workflow-monitor.sqlite`) or `supabase`.
`referral_pipeline start` always pins the same backend across the poll/API/approval
child process and sets `WORKFLOW_READ_EXISTING_REMOTE=1`, so a run started on sqlite
still **reads** cases that a previous run already wrote to Supabase — it just never
**creates** new cases there. The startup banner prints the active backend and warns
when the local job ledger shows a case was previously written remotely, so you know
to expect Assignment/attention to reflect cross-backend history for that case.

### Stage 2/3: assignment and handoff

`GET /api/workflow/assignments` lists Stage 2 work items (`assign-case-manager`) with
the configured case-manager roster. `POST /api/workflow/assignments/{case_id}/confirm`
records the decision, advances the case to Stage 3 (`awaiting_handoff`), and
**prepares** three `ExternalOperation`s — `notify-assigned-case-manager`,
`create-monday-record`, `prefill-drk-chart` — all left in `status: "ready"`. None of
them run automatically.

`GET /api/workflow/handoffs` lists those operations per case.
`POST /api/workflow/handoffs/{case_id}/preview` runs a dry-run of one operation.
`POST /api/workflow/handoffs/{case_id}/execute` performs the real action, gated per
operation type: Monday writes require `confirm: true` in the request body and are
otherwise rejected with `409`; DRK remains fill-only and never submits/creates.

### Workflow attention and deadlines

`GET /api/workflow/attention?stage=&limit=` is a read-only projection over stored
`attention_due_at` (cases) / `due_at` (work items) and open `wcw_workflow_exceptions`
— it never writes workflow state. Severity is `overdue`, `due_soon` (inside the
warning window), `blocked` (open exception), or `normal`. Per-step SLA durations
default from `DEMO_SLA_SECONDS` in `referral_pipeline/workflow/attention_policy.py`
and are **not confirmed WCW business rules** — override any step with
`WCW_SLA_<STEP_ID>_SECONDS` (e.g. `WCW_SLA_ASSIGN_CASE_MANAGER_SECONDS`) and the
due-soon window with `WCW_ATTENTION_WARNING_SECONDS`. A bulk reconciliation sweep
that backstops cases the per-confirmation apply path missed runs on the background
approval cycle, not on every read — it used to run inside `assignments()` and made
that endpoint take 50+ seconds under real case volume.

### Synthetic inbox-to-Monday rehearsal

The synthetic inbox fixtures contain no real patient data. They exercise four cases:
complete, missing threshold fields, incomplete supporting fields, and an exact duplicate.
The default flow only writes local artifacts under `tmp/`; it does not change Monday.

```powershell
$env:PYTHONPATH='src'
python src/monday.com/generate_synthetic_referrals.py
$eml = Get-ChildItem tmp/synthetic-referrals/emails/*.eml | Select-Object -ExpandProperty FullName
python src/referral_pipeline/runner.py `
  --eml $eml `
  --monday-mode snapshot `
  --monday-records-file tmp/synthetic-referrals/monday-snapshots/master_sheet_records.json `
  --agency-mode snapshot `
  --agency-records-file tmp/synthetic-referrals/monday-snapshots/accounts_records.json `
  --output-dir tmp/synthetic-inbox-run
python src/monday.com/evaluate_synthetic_replay.py `
  --fixture-dir tmp/synthetic-referrals `
  --run-dir tmp/synthetic-inbox-run
```

The full orchestration and system boundary are documented in
[src/referral_pipeline/README.md](src/referral_pipeline/README.md), while Outlook
configuration is in [src/Outlook/README.md](src/Outlook/README.md). The normal
manual-preview commands are:

```powershell
python run_pipeline.py outlook
python run_pipeline.py apply --confirm-master-sheet-write
```

The durable Stage 1 test-inbox path, acknowledgement gate, Supabase migration,
and read-only Monday/DRK checks are documented in
[docs/STAGE_ONE_INTAKE.md](docs/STAGE_ONE_INTAKE.md).

Step 4 scheduling monitoring and Step 5 visit monitoring are documented in
[docs/WORKFLOW_MONITORING.md](docs/WORKFLOW_MONITORING.md). They are read-only
against Monday and DRK; alerts and the continuous worker are separately opt-in.

The first command processes eligible new messages, performs read-only Monday and
agency lookups, and saves exact Master Sheet previews. The second command applies that
latest unblocked preview without rerunning extraction. For a controlled one-command
smoke test, use `outlook --apply --confirm-master-sheet-write`. The CLI creates its
own timestamped directory under `tmp/inbox-runs/`, remembers processed PDF hashes,
and prints progress by default. Add `--quiet` when only the final JSON summary is needed.

`python src/referral_pipeline/runner.py` and `push_master_sheet_plan.py` remain
available for debugging and batch/snapshot overrides. An explicit confirmation flag is
deliberately required before any Master Sheet item can be created. Do not apply
against WCW's live board without approval because item-creation automations fan out
to related boards.

For the email-based human review path, configure Microsoft Graph application
`Mail.Read` plus `Mail.Send` and backend Supabase credentials.
`REVIEW_RECIPIENT_EMAIL` is required and must be an internal intake-team address;
the detailed referral summary never falls back to the original sender:

```powershell
python run_pipeline.py stage-one-doctor --live
python run_pipeline.py outlook --send-review --max-messages 25
python run_pipeline.py retries
python run_pipeline.py failures
python run_pipeline.py approvals
python run_pipeline.py approvals --dry-run
# Real Monday create; DRK remains pending:
python run_pipeline.py approvals --execute
```

`--max-messages` counts eligible referral emails (newest first) and pages through
Outlook while the durable attachment ledger excludes known work. Permanent
failures stay failed until `python run_pipeline.py failures --requeue <sha256>`.
On Render, prefer the continuous background worker in `render.yaml` /
`run_worker.py` so SQLite state and PDF artifacts live on a persistent disk.

The review summary is rendered from the canonical extraction and sent to the
configured internal intake-team reviewer in the source Outlook conversation.
Unreplied threads are eligible for intake; transient Anthropic, Outlook, and Monday
failures are queued as `pending_retry` and drained by `retries`. The reviewer records
the outreach result with `Confirmed`, `No answer`, or `Information missing`.
Ambiguous wording is classified with OpenAI, while deterministic sender, thread,
message-time, seven-required-field, and artifact checks remain mandatory. The
default approval command only classifies replies; `--dry-run` validates without
writes; `--execute` creates the Monday item once. DRK automatic patient submission
is not implemented and remains a pending draft.

Supabase `referral_reviews` stores the correlated canonical, intake-plan, Monday,
and DRK JSON snapshots. `review_responses` records each Outlook response exactly
once and atomically updates its review status. RLS blocks client access; only the
worker's service-role credential can read or write these tables.

### How extraction works

For a given PDF:

- `--input-mode auto`: if `pdffonts` reports a usable text layer, we send extracted text; otherwise we send rendered page images.
- `--input-mode text`: force `pdfplumber` text extraction.
- `--input-mode image`: force Poppler-rendered page images.
- `--input-mode hybrid`: send both extracted text and rendered page images for the same selected pages.

Current default behavior is intentionally conservative:

- the first pass is the main extractor
- a header-focused repair pass may run for weak sender/contact fields
- a narrow requested-services repair pass may run for obviously weak multi-page service lists
- exact-field evidence is only used for suspicious values (for example combined phone fields or uncertain insurance IDs)

Schema:

- Claude is instructed to output JSON matching `ReferralIntake` (see `src/intake_extractor/models/schema.py`).
- Output is parsed as JSON and then validated with Pydantic. If JSON parsing fails, the runner retries once asking Claude to re-output strict JSON.

### Run: single PDF (prints JSON to terminal)

Example (auto-detect text vs vision):

```bash
PYTHONPATH=src python3.11 -m intake_extractor.llm.direct "samples/EC - REFERRAL FORM.pdf"
```

Force image mode (recommended for the scanned fax-style fixtures):

```bash
PYTHONPATH=src python3.11 -m intake_extractor.llm.direct "samples/EC - REFERRAL FORM.pdf" --input-mode image
```

Optional: cap pages sent (useful for long fax packets):

```bash
PYTHONPATH=src python3.11 -m intake_extractor.llm.direct "samples/fax20260711-48483-ougwp2.pdf" --max-pages 6
```

Force text extraction (useful for known text-layer PDFs):

```bash
PYTHONPATH=src python3.11 -m intake_extractor.llm.direct "samples/BUTLER, ALVA demo.pdf" --prefer-text
```

Send both text and images:

```bash
PYTHONPATH=src python3.11 -m intake_extractor.llm.direct "samples/fax20260711-48483-ougwp2.pdf" --input-mode hybrid
```

Write output to disk (still prints to stdout):

```bash
mkdir -p out
PYTHONPATH=src python3.11 -m intake_extractor.llm.direct "samples/EC - REFERRAL FORM.pdf" --write-out out
```

### Run: all fixtures (manual loop)

This will produce **PHI output in your terminal**.

```bash
mkdir -p out
for f in samples/*.pdf; do
  echo "=== $f ==="
  PYTHONPATH=src python3.11 -m intake_extractor.llm.direct "$f" --write-out out
done
```

### Outputs

- **stdout**: the normalized JSON (validated)
- **optional `--write-out out/`**: writes `out/<pdf_stem>.json`

### Evaluation

The repo includes a lightweight evaluator (see `eval/README.md` for flags and scoring details).

Run it with:

```bash
PYTHONPATH=src python3.11 -m intake_extractor.eval.evaluate
```

This will:

- materialize canonical gold JSON files under `eval/gold/`
- build `eval/manifest.csv`
- score the saved predictions under `out/`
- write reports to `out/eval-reports/`

Key reports:

- `out/eval-reports/per_run_scores.csv`
- `out/eval-reports/per_document_scores.csv`
- `out/eval-reports/mismatches.csv`
- `out/eval-reports/stability_by_field.csv`

### Monday referral push

The repo also includes a small bridge from `ReferralIntake` JSON into a Monday board row.

What it does:

- extracts one referral PDF with the same intake pipeline
- maps selected fields into configured Monday columns
- creates a new item when no match exists
- otherwise reuses an existing item by attached PDF filename first, then exact item name
- optionally uploads the source PDF into a Monday files column

The mapping is driven by `src/monday.com/referral_board_config.example.json`.

Dry run:

```bash
PYTHONPATH=src python3.11 src/monday.com/push_referral.py \
  "samples/EC - REFERRAL FORM.pdf" \
  --config src/monday.com/referral_board_config.example.json \
  --input-mode image \
  --write-out-dir out/monday-smoke \
  --dry-run
```

Live write:

```bash
PYTHONPATH=src python3.11 src/monday.com/push_referral.py \
  "samples/EC - REFERRAL FORM.pdf" \
  --config src/monday.com/referral_board_config.example.json \
  --input-mode image \
  --write-out-dir out/monday-smoke
```

Notes:

- progress logs go to `stderr` unless `--quiet` is used
- insurance can be mapped as either a text field or a dropdown via `insurance_provider_mode`
- placeholder all-same-digit phone numbers are skipped before writing to Monday
- reruns are upserts, not blind creates, as long as the configured files column or item name matches

### Tests

```bash
PYTHONPATH=src pytest -q tests/test_intake_extractor
# or everything under tests/
PYTHONPATH=src pytest -q tests
```

This covers page selection, input modes, postprocess cleanup, repair merges, reviewer patch policy, and evaluator behavior. See [`tests/README.md`](tests/README.md).

### Second-pass review (optional)

After a first-pass extraction folder exists, run a targeted patch-based reviewer:

```bash
PYTHONPATH=src python3.11 -m intake_extractor.review_tools.correct samples out/2026-07-17-run2 --out-dir out/2026-07-17-run2-reviewed
```

This writes corrected JSON under `--out-dir` and audit sidecars under `--out-dir/audit/` (`.review.json`, `.applied_patches.json`, `.audit.json`, plus folder `audit_summary.*`). The reviewer focuses on known weak fields (`requested_services`, diagnosis, referring contacts, address, referral date) and only applies gated patches.

### Known limitations


- **Direct JSON (no tool forcing)**: this runner relies on prompt discipline + Pydantic validation, not forced tool-use.

