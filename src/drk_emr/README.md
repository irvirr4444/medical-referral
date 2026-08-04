# DRK EMR

Python automation for [drkemr.com](https://drkemr.com).

| Folder | Purpose |
|---|---|
| [`read_patient/`](read_patient/) | Login, search patient by name, capture dashboard card JSON |
| [`create_patient/`](create_patient/) | Duplicate gate, then fill intake fields (never clicks Create Patient) |
| [`common/`](common/) | Shared browser helpers, patient search, models, redaction |

## Install

```bash
python3.11 -m pip install -r requirements.txt
```

Requires Google Chrome.

## Quick commands

```bash
# Read patient by name
PYTHONPATH=src python3.11 -m drk_emr.read_patient --output-dir output --lifetime-window 0

# Fill Create Patient form only after a clear duplicate gate (does not create)
PYTHONPATH=src python3.11 -m drk_emr.create_patient --output-dir output --hold-seconds 45
```

Copy root `.env.example` → `.env`, then see each folder’s `.env.example` for required vars.

## Duplicate gate

Before Patient Intake opens, create/fill searches `#patientSearchInput` and waits for a stable
`.summary` count:

- `0 results` and no rows → `clear_to_create`
- any candidate → verify DOB/MRN/phone/address/facility via search + demographics
- duplicate or ambiguous evidence → block fill/create (`fail closed`)

Audit artifact: `drk-duplicate-check.json` (mode `0600`). Create Patient submit remains disabled and
requires both `clear_to_create` and explicit confirmation even if re-enabled later.

## Tests

```bash
PYTHONPATH=src pytest -q tests/test_drk_emr
```

See [`tests/test_drk_emr/README.md`](../../tests/test_drk_emr/README.md).
