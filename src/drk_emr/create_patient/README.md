# Create Patient (Fill Only + Duplicate Gate)

Opens DRK **Patient Intake** and fills the form with synthetic TEST data (or future JSON input).

**Hard rules:**
1. Search the dashboard for the patient first and require `clear_to_create`.
2. Never click `#createPatientBtnBottom` / **Create Patient**.
3. Insurance save (`#saveInsuranceBtn`) is allowed; Create Patient submit is not.

## Command

```bash
PYTHONPATH=src python3.11 -m drk_emr.create_patient --output-dir output --hold-seconds 45
```

Optional flags:

| Flag | Default | Meaning |
|---|---|---|
| `--output-dir` | `output` | Base output directory |
| `--hold-seconds` | `90` | Keep browser open after fill so you can inspect |
| `--no-hold` | off | Close browser immediately after fill |
| `--skip-duplicate-check` | off | Unsafe offline escape hatch; do not use for real intake |

## `.env` variables

See [`.env.example`](.env.example). Put values in the **repo-root** `.env`.

| Variable | Type | Required | Meaning |
|---|---|---|---|
| `EMR_URL` | `string` (URL) | yes | EMR base or login URL |
| `EMR_USERNAME` | `string` | yes | EMR login username |
| `EMR_PASSWORD` | `string` | yes | EMR login password |

`TEST_PATIENT_NAME` / `TEST_PATIENT_ID` are **not** used here.

## What the script does

1. Login → land on `/Dashboard`
2. Type the patient name into `#patientSearchInput` and wait for a stable `.summary`
3. If `0 results` (or all candidates are conclusively different people) → continue
4. If any duplicate/suspicious/inconclusive candidate exists → abort before intake
5. Click Patients rail → **Create Patient** nav link → `/PatientIntake/Index`
6. Wait for lookup dropdowns (`GetLookupData`)
7. Fill demographics, addresses, contact, emergency, admission, referral
8. For typeaheads: type query → wait for `div.p-3.cursor-pointer` → click → confirm hidden id
9. Open insurance form, fill, optionally fill `#subscriberSection` when patient is not policy holder
10. Click insurance save (`#saveInsuranceBtn`) only
11. **Never** click Create Patient
12. Hold browser open for inspection; write:
    - `output/intake-fill-test/drk-duplicate-check.json`
    - `output/intake-fill-test/intake_fill_summary.json`

## Duplicate decision statuses

| Status | Meaning |
|---|---|
| `clear_to_create` | No matching patient; fill may proceed |
| `duplicate_found` | Name search hit confirmed by DOB or trusted MRN |
| `manual_review_required` | Ambiguous, conflicting, missing, or unstable evidence |
| `not_checked` | Gate was not run (aligned preview default) |

## Input datatypes

Full nested JSON contract: [`JSON_SCHEMA.md`](JSON_SCHEMA.md).

Current runtime payload: flat dataclass in [`synthetic_data.py`](synthetic_data.py) (`SyntheticIntakeData`).

Key type rules:

| Kind | Type | Notes |
|---|---|---|
| Names / addresses / free text | `string` | Prefer `TEST` markers for dry runs |
| Dates | `string` `YYYY-MM-DD` | Set via JS for reliability |
| Phones | `string` | e.g. `(555) 010-1111` |
| State | `string` | 2-letter code (`TX`) for select-by-value |
| Gender / language / relationship | `string` | Exact select option label |
| Booleans | `boolean` | Checkboxes / toggles |
| Typeahead `*_query` | `string` | Search text only; must match real EMR catalog rows |
| Money / percents | `string` or `number` | Copay, deductible, coverage |

## Code map

| File | Role |
|---|---|
| `duplicate_check.py` | Dashboard search + fail-closed match policy |
| `fill.py` | Navigation + fill + Create Patient hard block |
| `schema.py` | Typed create draft + duplicate decision models |
| `synthetic_data.py` | Default TEST payload |
| `adapters.py` | Synthetic → typed create draft |
| `JSON_SCHEMA.md` | Nested JSON field types and meanings |
| `__main__.py` | Enables `python -m drk_emr.create_patient` |

## Install reminder

```bash
python3.11 -m pip install -r requirements.txt
```

Needs Google Chrome.

## Tests

```bash
PYTHONPATH=src pytest -q tests/test_drk_emr/create_patient
```
