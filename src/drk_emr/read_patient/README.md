# Read Patient Info

Login to DRK EMR, find a patient **by name** (preferred) or ID, open the patient dashboard, capture the card APIs, and write JSON under `output/`.

## Command

```bash
PYTHONPATH=src python3.11 -m drk_emr.read_patient --output-dir output --lifetime-window 0
```

Optional flags:

| Flag | Default | Meaning |
|---|---|---|
| `--output-dir` | `output` | Base output directory |
| `--lifetime-window` | `0` | Cookie lifetime probe minutes (`0`, `5`, `15`, `60`). `0` = finish after fetch |
| `--print-catalog` | off | Print captured endpoint catalog to terminal (secrets masked) |

## `.env` variables

See [`.env.example`](.env.example). Put values in the **repo-root** `.env`.

| Variable | Type | Required | Meaning |
|---|---|---|---|
| `EMR_URL` | `string` (URL) | yes | EMR base or login URL, e.g. `https://drkemr.com` or `https://drkemr.com/Login/LoginView` |
| `EMR_USERNAME` | `string` | yes | EMR login username |
| `EMR_PASSWORD` | `string` | yes | EMR login password |
| `TEST_PATIENT_NAME` | `string` | preferred | Patient name; Last, First or First Last. Three-part names search the first two tokens. |
| `TEST_PATIENT_DOB` | `string` | when search has multiple rows | DOB used to pick the correct dropdown row |
| `TEST_PATIENT_PHONE` | `string` | optional | Phone used if DOB does not uniquely match |
| `TEST_PATIENT_MRN` | `string` | optional | MRN used if name/DOB/phone are not unique |
| `TEST_PATIENT_ID` | `string` | fallback | Numeric patient id if name is empty |

## What the script does

1. Opens Chrome and logs in  
2. On `/Dashboard`, searches given-name-first (three-part names use the first two tokens, e.g. `Anita Rodriguez Hernandez` → `Anita Rodriguez`), then opens the row that matches NAME / DOB / MRN / PHONE. It does not click the top match.
3. Resolves `patientId` from the URL  
4. Loads `/PatientDashboard/Index/?patientId=...`  
5. Captures same-host `application/json` responses  
6. Writes one JSON file per dashboard card  
7. If no diagnosis JSON API exists, scrapes `#diagnosisCard` DOM into `diagnosis.json`  

## Output location

```text
output/drk-browser-profile/<Patient_Name>/
  patient_information.json
  admission.json
  communications.json
  encounters.json
  diagnosis.json
  medications_allergies.json
  insurance.json
  custom_scans.json
  billing.json
  pipeline.json
  endpoint_catalog_<timestamp>.json
```

Example: `output/drk-browser-profile/Alva_Butler/`.

## Code map

| File | Role |
|---|---|
| `cli.py` | Main runner / CLI |
| `__main__.py` | Enables `python -m drk_emr.read_patient` |
| [`OUTPUT_SCHEMA.md`](OUTPUT_SCHEMA.md) | Datatypes for each output JSON card |
| [`../common/models.py`](../common/models.py) | `EndpointRecord`, replay models |
| [`../common/redaction.py`](../common/redaction.py) | Header/URL secret masking |

## Install reminder

```bash
python3.11 -m pip install -r requirements.txt
```

Needs Google Chrome installed (real browser automation via selenium-wire).

## Tests

```bash
PYTHONPATH=src pytest -q tests/test_drk_emr/read_patient
```
