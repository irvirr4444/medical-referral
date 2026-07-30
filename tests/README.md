# Tests layout

| Folder | Package under test |
|---|---|
| [`test_intake_extractor/`](test_intake_extractor/) | `src/intake_extractor/` |
| [`test_monday/`](test_monday/) | Monday push helpers (`src/monday.com/push_referral.py`) |
| [`test_drk_emr/`](test_drk_emr/) | `src/drk_emr/` |

Monday package-local tests remain at `src/monday.com/tests/`.

## Run all

```bash
PYTHONPATH=src pytest -q tests
```

## Run by area

```bash
PYTHONPATH=src pytest -q tests/test_intake_extractor
PYTHONPATH=src pytest -q tests/test_monday
PYTHONPATH=src pytest -q tests/test_drk_emr
```
