# Evaluation Set

This folder holds the committed configuration for the referral-extraction evaluator.

What lives here:

- `scoring_rules.json`: field-level metrics and weights (loaded via `--rules-path`)
- `gold/`: generated canonical gold records (written under `--eval-dir`)
- `manifest.csv`: generated manifest linking PDFs to gold records

## Run

```powershell
$env:PYTHONPATH = "src"
python -m intake_extractor.evaluate
```

Defaults:

| Flag | Default | Role |
|------|---------|------|
| `--gold-set` | newest `out/gold-set-*/gold_set_reviewed.json` (else `out/gold-set-2026-07-16/gold_set_reviewed.json`) | reviewed gold input |
| `--predictions-root` | `out/` | prediction run folders to score |
| `--eval-dir` | `eval/` | where gold JSON + `manifest.csv` are materialized |
| `--rules-path` | `eval/scoring_rules.json` | scoring rules (independent of `--eval-dir`) |
| `--reports-dir` | `out/eval-reports/` | CSV/JSON score reports |

`--eval-dir` only controls artifact output. Scoring rules always come from `--rules-path`, so pointing `--eval-dir` at a scratch folder does not require copying `scoring_rules.json`.

Example with explicit paths:

```powershell
$env:PYTHONPATH = "src"
python -m intake_extractor.evaluate `
  --gold-set out/gold-set-2026-07-16/gold_set_reviewed.json `
  --eval-dir eval `
  --rules-path eval/scoring_rules.json `
  --predictions-root out `
  --reports-dir out/eval-reports
```

## What the command does

1. materializes one canonical gold JSON per PDF under `<eval-dir>/gold/`
2. builds `<eval-dir>/manifest.csv`
3. scores every saved prediction run under `--predictions-root`
4. writes reports to `--reports-dir`

## Primary reports

- `out/eval-reports/per_run_scores.csv`
- `out/eval-reports/per_document_scores.csv`
- `out/eval-reports/mismatches.csv`
- `out/eval-reports/stability_by_field.csv`
- `out/eval-reports/summary.json`

## `requested_services` scoring

`requested_services` uses `service_list_match`: one-to-one list matching (lists are not collapsed by service name).

- Each row is compared on normalized service / frequency / instructions.
- Rows are paired with deterministic greedy best-match (service similarity required).
- Pair score weights: service `0.7`, frequency `0.15`, instructions `0.15`.
- Unmatched gold rows count as missing; unmatched predicted rows count as extra.
- Final field score is the F1 of precision/recall over those pair scores.
