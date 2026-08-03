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
- `src/intake_extractor/drk_pdf.py`: highest-accuracy native-PDF to DRK-card extractor
- `src/intake_extractor/drk_pdf_schema.py`: evidence-backed PDF extraction and DRK mapping schemas
- `src/intake_extractor/monday_pdf.py`: focused two-call PDF extraction for Monday intake
- `src/intake_extractor/monday_pdf_schema.py`: focused Master Sheet PDF facts plus `sent_by` contract
- `src/intake_extractor/aligned_intake.py`: canonical extraction adapters for Monday and DRK
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

### Highest-accuracy PDF → DRK card extraction

This path sends the original PDF to Anthropic as a native `application/pdf` document, so Claude receives both
the text and visual layout. The default uses `claude-opus-5`, adaptive thinking, maximum effort, and nine model
calls: two independent readings plus source adjudication for each of three smaller domains
(identity/referral, clinical lists, and insurance). The three domain pipelines run concurrently by default while
the two independent readings within each domain also run concurrently; adjudication waits for both readings.
This produces six concurrent reading calls followed by three concurrent adjudications. Use
`--sequential-domains` and/or `--sequential-readings` only for restrictive Anthropic rate limits.

The default transport is now `files-api`: the extractor uploads the PDF once, references the temporary
Anthropic file in all nine calls, and deletes it in a `finally` block after success or failure. The `inline`
transport remains available as an explicit fallback and sends base64 PDF bytes with each request. Transport
selection changes delivery only; both paths use the same model, prompts, schemas, passes, and adjudication.
See [the PDF transport policy](docs/PDF_TRANSPORT.md) for selection, fallback, PHI lifecycle, audit behavior,
the A/B accuracy observation, and troubleshooting.

```bash
PYTHONPATH=src python3.11 -m intake_extractor.drk_pdf \
  "samples/BUTLER, ALVA demo.pdf" \
  --output-dir output/pdf-drk-profile \
  --passes 3
```

The patient folder contains the same card filenames as the DRK reader:

- `patient_information.json`
- `admission.json`
- `communications.json`
- `encounters.json`
- `diagnosis.json`
- `medications_allergies.json`
- `insurance.json`
- `custom_scans.json`
- `billing.json`
- `pipeline.json`

It also writes `_extraction.json` with page-level evidence and warnings, plus `_manifest.json` with the source
SHA-256, model, effort, and pass count. DRK-generated IDs and workflow state are never invented: absent values
remain `null`, and cards unavailable from the PDF have `record_count: 0`.

Optional environment overrides:

```dotenv
ANTHROPIC_PDF_MODEL=claude-opus-5
ANTHROPIC_PDF_EFFORT=max
ANTHROPIC_PDF_MAX_TOKENS=32000
ANTHROPIC_PDF_TRANSPORT=files-api
```

Inline native-PDF requests are limited to 23 MB in this implementation, leaving room under Anthropic's 32 MB
request limit after base64 and JSON overhead.

To use the retained inline fallback for one run:

```bash
PYTHONPATH=src python3.11 -m intake_extractor.drk_pdf \
  "samples/BUTLER, ALVA demo.pdf" \
  --pdf-transport inline
```

Fallback is explicit rather than automatic so a Files API permission or cleanup failure is not hidden and nine
expensive model calls are not silently repeated.

### Focused two-call PDF → Monday contract

When only Monday intake is needed, do not wait for the full DRK clinical record. The focused contract uses two
sequential Opus calls: one complete PDF reading and one independent source verification. It covers every
intake-relevant Master Sheet fact that can reasonably come from a referral PDF:

- patient name, date of birth, phone, email, and address
- referring agency and its contact name, phone, and email
- current home-health/hospice and its contact details, kept distinct from the referring agency
- place of service and whether a wound order is explicitly included
- concise wound/referral-relevant clinical information
- every actual insurance policy
- an explicit clinical referral/order/signature date

`sent_by` is supplied by the info-box/email workflow rather than inferred from the PDF. Scheduling, case-manager,
territory, contact-outcome, and status columns remain downstream workflow data. Both calls use the same focused
strict schema. The verifier corrects the first candidate against the source but does not expand the result into
complete medication or historical diagnosis lists.

```bash
PYTHONPATH=src python3.11 -m intake_extractor.monday_pdf \
  "samples/BUTLER, ALVA demo.pdf" \
  --sent-by "Intake Info Box" \
  --output-dir output/pdf-monday-intake
```

The command writes PHI-protected `monday-intake.json`, the existing-pipeline-compatible
`referral-intake.json`, and `_manifest.json`. It does not call Monday or create an item. The manifest records
the source hash, model, transport, and the two-call contract.

### Aligned PDF → parallel Monday + DRK handoffs

The aligned flow keeps the full `DrkPdfExtraction` as the canonical record, then derives two views from it:

1. `master_sheet_referral` for the existing Monday Master Sheet planner/writer
2. `drk_create_draft` matching the discovered DRK Patient Intake fields

Both are derived independently from the same canonical extraction and retain one correlation ID and source
SHA-256; neither target becomes the source for the other. Missing fields stay `null`; DRK catalog-backed fields
(payer, facility, place of service, and similar typeaheads) remain blockers until an exact DRK catalog match is
approved. Clinical referring-provider data is preserved but is not silently treated as the DRK assigned provider.

Build both previews from a completed high-accuracy extraction:

```bash
PYTHONPATH=src python3.11 src/monday.com/build_aligned_intake.py \
  --extraction-json "output/pdf-drk-profile/Patient_Name/_extraction.json" \
  --source-pdf "samples/referral.pdf" \
  --sent-by "Intake Info Box" \
  --config src/monday.com/master_sheet_write_config.example.json
```

Or extract and build the previews in one command:

```bash
PYTHONPATH=src python3.11 src/monday.com/build_aligned_intake.py \
  --pdf "samples/referral.pdf" \
  --passes 3
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

Run the intake extractor test suite with:

```bash
PYTHONPATH=src pytest -q tests
```

This covers page selection, input modes, postprocess cleanup, repair merges, reviewer patch policy, and evaluator behavior.

### Second-pass review (optional)

After a first-pass extraction folder exists, run a targeted patch-based reviewer:

```bash
PYTHONPATH=src python3.11 -m intake_extractor.review_tools.correct samples out/2026-07-17-run2 --out-dir out/2026-07-17-run2-reviewed
```

This writes corrected JSON under `--out-dir` and audit sidecars under `--out-dir/audit/` (`.review.json`, `.applied_patches.json`, `.audit.json`, plus folder `audit_summary.*`). The reviewer focuses on known weak fields (`requested_services`, diagnosis, referring contacts, address, referral date) and only applies gated patches.

### Known limitations


- **Direct JSON (no tool forcing)**: this runner relies on prompt discipline + Pydantic validation, not forced tool-use.

