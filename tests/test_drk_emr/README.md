# DRK EMR tests

Mirrors `src/drk_emr/` layout. Named `test_drk_emr` (not `drk_emr`) so pytest does not shadow the real package under `src/`.

| Folder | Covers |
|---|---|
| [`common/`](common/) | Redaction / URL masking (`drk_emr.common`) |
| [`read_patient/`](read_patient/) | Dashboard read helpers (`drk_emr.read_patient`) |
| [`create_patient/`](create_patient/) | Fill-only guards, duplicate gate, synthetic TEST data |

## Commands

```bash
# All DRK EMR unit tests
PYTHONPATH=src pytest -q tests/test_drk_emr

# By area
PYTHONPATH=src pytest -q tests/test_drk_emr/common
PYTHONPATH=src pytest -q tests/test_drk_emr/read_patient
PYTHONPATH=src pytest -q tests/test_drk_emr/create_patient
```

These are unit tests only (no live Chrome login and no Create Patient submission). Live runs use the package CLIs under `src/drk_emr/`.
