## medical-referral

Pipeline to extract **one normalized JSON record per referral/intake PDF** (digital forms, scanned faxes, EHR printouts) using Claude.

### PHI / safety

These PDFs contain **PHI**.

- **Do not commit generated outputs**. The `out/` folder is gitignored.
- `llm_direct.py` **prints the extracted JSON to stdout by default** (this will include PHI).

### Project structure (current)

- `samples/`: 7 reference PDFs (fixtures)
- `src/intake_extractor/schema.py`: Pydantic schema (`ReferralIntake`)
- `src/intake_extractor/llm_direct.py`: main extraction runner
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

### Synthetic inbox-to-Monday rehearsal

The synthetic inbox fixtures contain no real patient data. They exercise four cases:
complete, missing threshold fields, incomplete supporting fields, and an exact duplicate.
The default flow only writes local artifacts under `tmp/`; it does not change Monday.

```powershell
$env:PYTHONPATH='src'
python src/monday.com/generate_synthetic_referrals.py
$eml = Get-ChildItem tmp/synthetic-referrals/emails/*.eml | Select-Object -ExpandProperty FullName
python src/monday.com/run_inbound_intake.py `
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

To connect a test Outlook mailbox, create an Entra application with **read-only**
Microsoft Graph `Mail.Read` application permission and mailbox-scoped access, then
set these values in `.env`: `OUTLOOK_TENANT_ID`, `OUTLOOK_CLIENT_ID`,
`OUTLOOK_CLIENT_SECRET`, and `OUTLOOK_MAILBOX`. The poller accepts only attachments
whose filename ends in `.pdf` and whose file bytes contain a PDF signature:

```powershell
python src/monday.com/run_inbound_intake.py --outlook-poll --max-messages 10
```

`--master-sheet-mode apply --confirm-master-sheet-write` is deliberately required
before any Master Sheet item can be created. Do not use it against WCW's live board
until an owner approves a controlled synthetic smoke test, because item-creation
automations fan out to related boards.

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

- Claude is instructed to output JSON matching `ReferralIntake` (see `src/intake_extractor/schema.py`).
- Output is parsed as JSON and then validated with Pydantic. If JSON parsing fails, the runner retries once asking Claude to re-output strict JSON.

### Run: single PDF (prints JSON to terminal)

Example (auto-detect text vs vision):

```bash
PYTHONPATH=src python3.11 -m intake_extractor.llm_direct "samples/EC - REFERRAL FORM.pdf"
```

Force image mode (recommended for the scanned fax-style fixtures):

```bash
PYTHONPATH=src python3.11 -m intake_extractor.llm_direct "samples/EC - REFERRAL FORM.pdf" --input-mode image
```

Optional: cap pages sent (useful for long fax packets):

```bash
PYTHONPATH=src python3.11 -m intake_extractor.llm_direct "samples/fax20260711-48483-ougwp2.pdf" --max-pages 6
```

Force text extraction (useful for known text-layer PDFs):

```bash
PYTHONPATH=src python3.11 -m intake_extractor.llm_direct "samples/BUTLER, ALVA demo.pdf" --prefer-text
```

Send both text and images:

```bash
PYTHONPATH=src python3.11 -m intake_extractor.llm_direct "samples/fax20260711-48483-ougwp2.pdf" --input-mode hybrid
```

Write output to disk (still prints to stdout):

```bash
mkdir -p out
PYTHONPATH=src python3.11 -m intake_extractor.llm_direct "samples/EC - REFERRAL FORM.pdf" --write-out out
```

### Run: all fixtures (manual loop)

This will produce **PHI output in your terminal**.

```bash
mkdir -p out
for f in samples/*.pdf; do
  echo "=== $f ==="
  PYTHONPATH=src python3.11 -m intake_extractor.llm_direct "$f" --write-out out
done
```

### Outputs

- **stdout**: the normalized JSON (validated)
- **optional `--write-out out/`**: writes `out/<pdf_stem>.json`

### Evaluation

The repo includes a lightweight evaluator (see `eval/README.md` for flags and scoring details).

Run it with:

```bash
PYTHONPATH=src python3.11 -m intake_extractor.evaluate
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

Run the intake extractor test suite with:

```bash
PYTHONPATH=src pytest -q tests
```

This covers page selection, input modes, postprocess cleanup, repair merges, reviewer patch policy, and evaluator behavior.

### Second-pass review (optional)

After a first-pass extraction folder exists, run a targeted patch-based reviewer:

```bash
PYTHONPATH=src python3.11 -m intake_extractor.review_correct samples out/2026-07-17-run2 --out-dir out/2026-07-17-run2-reviewed
```

This writes corrected JSON under `--out-dir` and audit sidecars under `--out-dir/audit/` (`.review.json`, `.applied_patches.json`, `.audit.json`, plus folder `audit_summary.*`). The reviewer focuses on known weak fields (`requested_services`, diagnosis, referring contacts, address, referral date) and only applies gated patches.

### Known limitations


- **Direct JSON (no tool forcing)**: this runner relies on prompt discipline + Pydantic validation, not forced tool-use.

