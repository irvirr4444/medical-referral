# Monday.com tests (repo `tests/` tree)

Unit tests that live under `tests/` for Monday referral push helpers.

> Most Monday API live/unit tests already live next to the package:  
> `src/monday.com/tests/`

| Folder | Covers |
|---|---|
| [`push/`](push/) | `push_referral.py` formatting / mapping helpers |

## Commands

```bash
# This folder
PYTHONPATH=src pytest -q tests/test_monday

# Package-local Monday tests
PYTHONPATH=src pytest -q src/monday.com/tests -k unit
```
