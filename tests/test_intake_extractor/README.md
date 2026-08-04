# Intake extractor tests

Mirrors areas under `src/intake_extractor/`. Named `test_intake_extractor` so it does not shadow the package.

| Folder | Covers |
|---|---|
| [`evaluate/`](evaluate/) | Scoring / eval helpers |
| [`evidence/`](evidence/) | Extraction evidence guide |
| [`pdf/`](pdf/) | PDF input modes + user content |
| [`postprocess/`](postprocess/) | Referral normalization |
| [`repair/`](repair/) | Repair merge / trigger logic |
| [`review/`](review/) | Reviewer patches + policy/audit |
| [`selection/`](selection/) | Page selection |

## Commands

```bash
# All intake-extractor unit tests
PYTHONPATH=src pytest -q tests/test_intake_extractor

# By area
PYTHONPATH=src pytest -q tests/test_intake_extractor/evaluate
PYTHONPATH=src pytest -q tests/test_intake_extractor/review
PYTHONPATH=src pytest -q tests/test_intake_extractor/selection
```
