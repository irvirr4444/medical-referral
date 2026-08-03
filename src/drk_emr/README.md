# DRK EMR

Python automation for [drkemr.com](https://drkemr.com).

| Folder | Purpose |
|---|---|
| [`read_patient/`](read_patient/) | Login, search patient by name, capture dashboard card JSON |
| [`create_patient/`](create_patient/) | Login, open intake form, fill fields (never clicks Create Patient) |
| [`common/`](common/) | Shared models + secret redaction |

## Install

```bash
python3.11 -m pip install -r requirements.txt
```

Requires Google Chrome.

## Quick commands

```bash
# Read patient by name
PYTHONPATH=src python3.11 -m drk_emr.read_patient --output-dir output --lifetime-window 0

# Fill Create Patient form only (does not create)
PYTHONPATH=src python3.11 -m drk_emr.create_patient --output-dir output --hold-seconds 45
```

Copy root `.env.example` → `.env`, then see each folder’s `.env.example` for required vars.

## Tests

```bash
PYTHONPATH=src pytest -q tests/test_drk_emr
```

See [`tests/test_drk_emr/README.md`](../../tests/test_drk_emr/README.md).
