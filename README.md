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

