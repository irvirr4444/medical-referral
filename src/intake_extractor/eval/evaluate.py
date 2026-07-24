from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_PREDICTIONS_ROOT = Path("out")
DEFAULT_EVAL_DIR = Path("eval")
DEFAULT_RULES_PATH = DEFAULT_EVAL_DIR / "scoring_rules.json"
DEFAULT_REPORTS_DIR = Path("out/eval-reports")
# Fallback when no out/gold-set-*/gold_set_reviewed.json is discoverable.
FALLBACK_GOLD_SET = Path("out/gold-set-2026-07-16/gold_set_reviewed.json")

PUNCT_RE = re.compile(r"[^a-z0-9]+")
DATE_RE = re.compile(r"^\s*(\d{1,2})/(\d{1,2})/(\d{2}|\d{4})\s*$")
ICD_RE = re.compile(r"[^A-Z0-9.]")

# Pair scoring: service dominates; frequency/instructions are secondary attachments.
_SERVICE_PAIR_WEIGHT = 0.7
_FREQUENCY_PAIR_WEIGHT = 0.15
_INSTRUCTIONS_PAIR_WEIGHT = 0.15


@dataclass(frozen=True)
class FieldResult:
    field: str
    score: float
    weight: float
    metric: str
    expected: Any
    actual: Any
    detail: str


@dataclass(frozen=True)
class _NormalizedService:
    index: int
    service: str | None
    frequency: str | None
    instructions: str | None
    label: str


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _slugify(stem: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", stem).strip("_")
    return slug or "record"


def _normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    return " ".join(PUNCT_RE.sub(" ", text).split())


def _normalize_phone(value: Any) -> str | None:
    if value is None:
        return None
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return digits or None


def _normalize_date(value: Any) -> str | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    match = DATE_RE.match(raw)
    if not match:
        return raw.lower()
    month, day, year = match.groups()
    year_int = int(year)
    if len(year) == 2:
        year_int += 2000 if year_int <= 69 else 1900
    return f"{year_int:04d}-{int(month):02d}-{int(day):02d}"


def _normalize_icd(code: str) -> str:
    return ICD_RE.sub("", code.upper())


def _tokenize(value: Any) -> set[str]:
    normalized = _normalize_text(value)
    return set(normalized.split()) if normalized else set()


def _string_similarity(expected: Any, actual: Any) -> float:
    if expected is None and actual is None:
        return 1.0
    if expected is None or actual is None:
        return 0.0
    if _normalize_text(expected) == _normalize_text(actual):
        return 1.0
    left = _tokenize(expected)
    right = _tokenize(actual)
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    overlap = len(left & right)
    precision = overlap / len(right)
    recall = overlap / len(left)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _set_f1(expected: list[str], actual: list[str], *, normalizer=lambda x: x) -> float:
    left = {normalizer(item) for item in expected if item is not None}
    right = {normalizer(item) for item in actual if item is not None}
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    overlap = len(left & right)
    precision = overlap / len(right)
    recall = overlap / len(left)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _normalize_service_name(value: Any) -> str | None:
    normalized = _normalize_text(value)
    if not normalized:
        return None
    replacements = {
        "home health outpatient": "home health",
        "home hlth": "home health",
        "dme": "durable medical equipment",
    }
    for needle, repl in replacements.items():
        normalized = normalized.replace(needle, repl)
    return normalized


def _service_label(item: dict[str, Any]) -> str:
    service = item.get("service")
    if service is None or not str(service).strip():
        return "<missing service>"
    return str(service).strip()


def _normalize_service_item(index: int, item: dict[str, Any]) -> _NormalizedService:
    return _NormalizedService(
        index=index,
        service=_normalize_service_name(item.get("service")),
        frequency=_normalize_text(item.get("frequency")),
        instructions=_normalize_text(item.get("instructions")),
        label=_service_label(item),
    )


def _service_pair_score(
    expected: _NormalizedService, actual: _NormalizedService
) -> tuple[float, float, float, float]:
    service_sim = _string_similarity(expected.service, actual.service)
    frequency_sim = _string_similarity(expected.frequency, actual.frequency)
    instructions_sim = _string_similarity(expected.instructions, actual.instructions)
    pair_score = (
        _SERVICE_PAIR_WEIGHT * service_sim
        + _FREQUENCY_PAIR_WEIGHT * frequency_sim
        + _INSTRUCTIONS_PAIR_WEIGHT * instructions_sim
    )
    return pair_score, service_sim, frequency_sim, instructions_sim


def _score_requested_services(expected: list[dict[str, Any]], actual: list[dict[str, Any]]) -> tuple[float, str]:
    """Score requested_services with one-to-one list matching.

    Lists are preserved (duplicates are not collapsed). Matching is greedy best-match:
    all candidate pairs are scored, sorted deterministically by descending pair score
    (then service similarity, then indices), and assigned without reuse. Pairs with no
    service overlap are never matched so unrelated rows stay missing/extra.
    """
    expected_items = [_normalize_service_item(i, item) for i, item in enumerate(expected)]
    actual_items = [_normalize_service_item(i, item) for i, item in enumerate(actual)]

    if not expected_items and not actual_items:
        return 1.0, "both lists empty"

    # Candidate edges: require some service similarity so we do not pair unrelated rows.
    candidates: list[tuple[float, float, int, int, float, float]] = []
    for exp in expected_items:
        for act in actual_items:
            pair_score, service_sim, frequency_sim, instructions_sim = _service_pair_score(exp, act)
            if service_sim <= 0.0:
                continue
            candidates.append((pair_score, service_sim, exp.index, act.index, frequency_sim, instructions_sim))

    # Deterministic greedy assignment: best pair first, each index used at most once.
    candidates.sort(key=lambda row: (-row[0], -row[1], row[2], row[3]))
    matched_expected: set[int] = set()
    matched_actual: set[int] = set()
    match_scores: list[float] = []
    match_service: list[float] = []
    match_frequency: list[float] = []
    match_instructions: list[float] = []

    for pair_score, service_sim, exp_idx, act_idx, frequency_sim, instructions_sim in candidates:
        if exp_idx in matched_expected or act_idx in matched_actual:
            continue
        matched_expected.add(exp_idx)
        matched_actual.add(act_idx)
        match_scores.append(pair_score)
        match_service.append(service_sim)
        match_frequency.append(frequency_sim)
        match_instructions.append(instructions_sim)

    missing = [item.label for item in expected_items if item.index not in matched_expected]
    extra = [item.label for item in actual_items if item.index not in matched_actual]
    score_sum = sum(match_scores)

    # Unmatched gold rows hurt recall; unmatched predicted rows hurt precision.
    recall = score_sum / len(expected_items) if expected_items else 1.0
    precision = score_sum / len(actual_items) if actual_items else 1.0
    if precision + recall == 0:
        score = 0.0
    else:
        score = 2 * precision * recall / (precision + recall)

    avg_service = sum(match_service) / len(match_service) if match_service else 0.0
    avg_frequency = sum(match_frequency) / len(match_frequency) if match_frequency else 0.0
    avg_instructions = sum(match_instructions) / len(match_instructions) if match_instructions else 0.0
    detail = (
        f"matched={len(match_scores)}/{len(expected_items)}; "
        f"precision={precision:.3f}; recall={recall:.3f}; "
        f"avg_service={avg_service:.3f}; avg_frequency={avg_frequency:.3f}; "
        f"avg_instructions={avg_instructions:.3f}; "
        f"missing={missing}; extra={extra}"
    )
    return score, detail


def _compare_field(field: str, rule: dict[str, Any], expected: Any, actual: Any) -> FieldResult:
    metric = rule["type"]
    weight = float(rule["weight"])

    if metric == "normalized_exact":
        score = 1.0 if _normalize_text(expected) == _normalize_text(actual) else 0.0
        detail = "normalized exact match"
    elif metric == "phone_exact":
        score = 1.0 if _normalize_phone(expected) == _normalize_phone(actual) else 0.0
        detail = "digit-only phone match"
    elif metric == "date_exact":
        score = 1.0 if _normalize_date(expected) == _normalize_date(actual) else 0.0
        detail = "normalized date match"
    elif metric == "normalized_string":
        score = _string_similarity(expected, actual)
        detail = "token overlap string similarity"
    elif metric == "token_overlap":
        score = _string_similarity(expected, actual)
        detail = "token F1 overlap"
    elif metric == "set_f1":
        score = _set_f1(expected or [], actual or [], normalizer=_normalize_icd)
        detail = "set F1"
    elif metric == "service_list_match":
        score, detail = _score_requested_services(expected or [], actual or [])
    elif metric == "optional_text":
        score = _string_similarity(expected, actual)
        detail = "low-weight optional text overlap"
    elif metric == "ignored":
        score = 1.0
        detail = "ignored metadata field"
    else:
        raise ValueError(f"Unsupported metric: {metric}")

    return FieldResult(
        field=field,
        score=score,
        weight=weight,
        metric=metric,
        expected=expected,
        actual=actual,
        detail=detail,
    )


def _materialize_gold(gold_payload: dict[str, Any], eval_dir: Path) -> list[dict[str, Any]]:
    gold_dir = eval_dir / "gold"
    gold_dir.mkdir(parents=True, exist_ok=True)

    manifest_rows: list[dict[str, Any]] = []
    for record in gold_payload["records"]:
        pdf_name = record["pdf_name"]
        pdf_stem = pdf_name.removesuffix(".json")
        slug = _slugify(pdf_stem)
        gold_path = gold_dir / f"{slug}.gold.json"
        payload = {
            "pdf_name": pdf_name,
            "review_status": record["review_status"],
            "review_confidence": record["review_confidence"],
            "review_notes": record["review_notes"],
            "record": record["candidate_record"],
        }
        _write_json(gold_path, payload)
        manifest_rows.append(
            {
                "pdf_name": pdf_name,
                "pdf_path": str(Path("samples") / f"{pdf_stem}.pdf"),
                "gold_json_path": str(gold_path),
                "review_status": record["review_status"],
                "review_confidence": record["review_confidence"],
                "review_notes": record["review_notes"],
            }
        )

    manifest_path = eval_dir / "manifest.csv"
    with manifest_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(manifest_rows[0].keys()))
        writer.writeheader()
        writer.writerows(manifest_rows)

    return manifest_rows


def _discover_predictions(predictions_root: Path, gold_names: set[str]) -> dict[str, dict[str, Path]]:
    predictions: dict[str, dict[str, Path]] = {}

    root_level = {path.name: path for path in predictions_root.glob("*.json") if path.name in gold_names}
    if root_level:
        predictions["baseline-root"] = root_level

    for directory in sorted(predictions_root.iterdir()):
        if not directory.is_dir():
            continue
        if directory.name.startswith("gold-set") or directory.name == "eval-reports":
            continue
        files = {path.name: path for path in directory.glob("*.json") if path.name in gold_names}
        if files:
            predictions[directory.name] = files

    return predictions


def _critical_failures(record: dict[str, Any], prediction: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    critical_fields = {
        "patient_name": _normalize_text,
        "patient_dob": _normalize_date,
        "insurance_id": _normalize_text,
    }
    for field, normalizer in critical_fields.items():
        if normalizer(record.get(field)) != normalizer(prediction.get(field)):
            failures.append(field)
    return failures


def _evaluate(
    gold_payload: dict[str, Any],
    rules: dict[str, dict[str, Any]],
    predictions_root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    gold_records = {record["pdf_name"]: record for record in gold_payload["records"]}
    prediction_index = _discover_predictions(predictions_root, set(gold_records))

    per_document_rows: list[dict[str, Any]] = []
    mismatch_rows: list[dict[str, Any]] = []
    stability_rows: list[dict[str, Any]] = []

    field_value_tracker: dict[str, dict[str, Counter[str]]] = defaultdict(lambda: defaultdict(Counter))

    for run_name, documents in prediction_index.items():
        for pdf_name, gold_record in gold_records.items():
            gold_data = gold_record["candidate_record"]
            pred_path = documents.get(pdf_name)
            if pred_path is None:
                per_document_rows.append(
                    {
                        "run_name": run_name,
                        "pdf_name": pdf_name,
                        "prediction_path": "",
                        "overall_score": 0.0,
                        "weighted_score_percent": 0.0,
                        "matched_fields": 0,
                        "field_count": len(rules),
                        "critical_failures": "missing_prediction",
                        "review_confidence": gold_record["review_confidence"],
                        "missing_prediction": True,
                    }
                )
                mismatch_rows.append(
                    {
                        "run_name": run_name,
                        "pdf_name": pdf_name,
                        "field": "__document__",
                        "metric": "missing_prediction",
                        "score": 0.0,
                        "expected": "",
                        "actual": "",
                        "detail": "Prediction file missing for this document.",
                    }
                )
                continue

            prediction = _load_json(pred_path)
            total_weight = 0.0
            total_score = 0.0
            matched_fields = 0

            for field, rule in rules.items():
                expected = gold_data.get(field)
                actual = prediction.get(field)
                result = _compare_field(field, rule, expected, actual)
                total_weight += result.weight
                total_score += result.score * result.weight
                if math.isclose(result.score, 1.0, abs_tol=1e-9):
                    matched_fields += 1
                else:
                    mismatch_rows.append(
                        {
                            "run_name": run_name,
                            "pdf_name": pdf_name,
                            "field": field,
                            "metric": result.metric,
                            "score": round(result.score, 4),
                            "expected": json.dumps(result.expected, ensure_ascii=False, sort_keys=True),
                            "actual": json.dumps(result.actual, ensure_ascii=False, sort_keys=True),
                            "detail": result.detail,
                        }
                    )

                if result.metric != "ignored":
                    field_value_tracker[pdf_name][field][json.dumps(actual, ensure_ascii=False, sort_keys=True)] += 1

            weighted_score = total_score / total_weight if total_weight else 0.0
            failures = _critical_failures(gold_data, prediction)
            per_document_rows.append(
                {
                    "run_name": run_name,
                    "pdf_name": pdf_name,
                    "prediction_path": str(pred_path),
                    "overall_score": round(weighted_score, 4),
                    "weighted_score_percent": round(weighted_score * 100, 2),
                    "matched_fields": matched_fields,
                    "field_count": len(rules),
                    "critical_failures": ";".join(failures),
                    "review_confidence": gold_record["review_confidence"],
                    "missing_prediction": False,
                }
            )

    by_run: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in per_document_rows:
        by_run[row["run_name"]].append(row)

    per_run_rows: list[dict[str, Any]] = []
    for run_name, rows in sorted(by_run.items()):
        scores = [row["overall_score"] for row in rows]
        coverage = sum(0 if row["missing_prediction"] else 1 for row in rows)
        criticals = sum(1 for row in rows if row["critical_failures"])
        per_run_rows.append(
            {
                "run_name": run_name,
                "documents_scored": len(rows),
                "documents_present": coverage,
                "coverage_percent": round((coverage / len(rows)) * 100, 2) if rows else 0.0,
                "average_score": round(sum(scores) / len(scores), 4) if scores else 0.0,
                "median_score": round(sorted(scores)[len(scores) // 2], 4) if scores else 0.0,
                "critical_failure_docs": criticals,
            }
        )

    for pdf_name, field_counters in sorted(field_value_tracker.items()):
        for field, counter in sorted(field_counters.items()):
            total = sum(counter.values())
            top_value, top_support = counter.most_common(1)[0]
            stability_rows.append(
                {
                    "pdf_name": pdf_name,
                    "field": field,
                    "distinct_values_seen": len(counter),
                    "most_common_support": top_support,
                    "runs_with_value": total,
                    "stability_ratio": round(top_support / total, 4) if total else 0.0,
                    "most_common_value": top_value,
                }
            )

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "gold_record_count": len(gold_records),
        "run_count": len(per_run_rows),
        "prediction_sources": sorted(prediction_index),
        "average_run_score": round(sum(row["average_score"] for row in per_run_rows) / len(per_run_rows), 4)
        if per_run_rows
        else 0.0,
        "best_run": max(per_run_rows, key=lambda row: row["average_score"], default=None),
        "worst_run": min(per_run_rows, key=lambda row: row["average_score"], default=None),
        "documents_with_any_mismatch": len({row["pdf_name"] for row in mismatch_rows if row["field"] != "__document__"}),
        "mismatch_count": len(mismatch_rows),
    }
    return per_run_rows, per_document_rows, mismatch_rows, {"summary": summary, "stability": stability_rows}


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _load_rules(rules_path: Path) -> dict[str, dict[str, Any]]:
    if not rules_path.exists():
        raise FileNotFoundError(f"Scoring rules not found: {rules_path}")
    return _load_json(rules_path)


def _discover_default_gold_set() -> Path:
    """Prefer the newest out/gold-set-*/gold_set_reviewed.json; else the known fallback path."""
    root = Path("out")
    if root.is_dir():
        discovered = sorted(root.glob("gold-set-*/gold_set_reviewed.json"))
        if discovered:
            return discovered[-1]
    return FALLBACK_GOLD_SET


def main() -> None:
    parser = argparse.ArgumentParser(description="Materialize and score a referral-extraction evaluation set.")
    parser.add_argument(
        "--gold-set",
        type=Path,
        default=None,
        help=(
            "Path to reviewed gold_set JSON. "
            f"Default: newest out/gold-set-*/gold_set_reviewed.json, else {FALLBACK_GOLD_SET}."
        ),
    )
    parser.add_argument("--predictions-root", type=Path, default=DEFAULT_PREDICTIONS_ROOT)
    parser.add_argument(
        "--eval-dir",
        type=Path,
        default=DEFAULT_EVAL_DIR,
        help="Directory for materialized gold JSON and manifest.csv (default: eval/).",
    )
    parser.add_argument(
        "--rules-path",
        type=Path,
        default=DEFAULT_RULES_PATH,
        help=f"Path to scoring_rules.json (default: {DEFAULT_RULES_PATH}). Independent of --eval-dir.",
    )
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR)
    args = parser.parse_args()

    gold_set_path = args.gold_set or _discover_default_gold_set()
    gold_payload = _load_json(gold_set_path)
    args.eval_dir.mkdir(parents=True, exist_ok=True)
    args.reports_dir.mkdir(parents=True, exist_ok=True)

    manifest_rows = _materialize_gold(gold_payload, args.eval_dir)
    rules = _load_rules(args.rules_path)
    per_run_rows, per_document_rows, mismatch_rows, extra_payload = _evaluate(gold_payload, rules, args.predictions_root)

    _write_csv(args.reports_dir / "per_run_scores.csv", per_run_rows)
    _write_csv(args.reports_dir / "per_document_scores.csv", per_document_rows)
    _write_csv(args.reports_dir / "mismatches.csv", mismatch_rows)
    _write_csv(args.reports_dir / "stability_by_field.csv", extra_payload["stability"])

    summary_payload = {
        "summary": extra_payload["summary"],
        "manifest_count": len(manifest_rows),
        "gold_set_path": str(gold_set_path),
        "rules_path": str(args.rules_path),
        "eval_dir": str(args.eval_dir),
        "reports_dir": str(args.reports_dir),
    }
    _write_json(args.reports_dir / "summary.json", summary_payload)

    print(f"Loaded gold set from {gold_set_path}")
    print(f"Loaded scoring rules from {args.rules_path}")
    print(f"Materialized gold manifest at {args.eval_dir / 'manifest.csv'}")
    print(f"Wrote per-run report to {args.reports_dir / 'per_run_scores.csv'}")
    print(f"Wrote per-document report to {args.reports_dir / 'per_document_scores.csv'}")
    print(f"Wrote mismatch report to {args.reports_dir / 'mismatches.csv'}")
    print(f"Wrote stability report to {args.reports_dir / 'stability_by_field.csv'}")
    print(f"Wrote summary to {args.reports_dir / 'summary.json'}")


if __name__ == "__main__":
    main()

