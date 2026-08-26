"""One-shot Anthropic expansion/cleanup of committed synthetic vocabulary banks.

Runtime PDF generation never calls this module. Re-run only when banks need growth.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from intake_extractor.llm.anthropic_json import AnthropicJsonError, build_client, call_model_for_json

from .vocab_rules import (
    DATA_PATH,
    ICD_RE,
    LEAK_RE,
    NAME_RE,
    SIZE_FLOORS,
    WITHDRAWN_MEDS,
    diagnosis_family_errors,
    failing_diagnoses,
    validate_vocabulary_payload,
)


DEFAULT_MODEL = os.getenv("ANTHROPIC_VOCAB_MODEL", "claude-sonnet-4-5-20250929")

TARGETS = {
    "first_names": SIZE_FLOORS["first_names"],
    "last_names": SIZE_FLOORS["last_names"],
    "facilities": SIZE_FLOORS["facilities"],
    "insurers": SIZE_FLOORS["insurers"],
    "medications": SIZE_FLOORS["medications"],
    "note_fragments": SIZE_FLOORS["note_fragments"],
    "diagnoses": SIZE_FLOORS["diagnoses"],
    "service_instructions": SIZE_FLOORS["service_instructions"],
    "service_frequencies": SIZE_FLOORS["service_frequencies"],
    "street_names": SIZE_FLOORS["street_names"],
    "cities": SIZE_FLOORS["cities"],
}

SYSTEM_PROMPT = """\
You expand FICTITIOUS vocabulary banks for wound-care referral synthetic data.
Return one JSON object only. No markdown. No commentary.
All people and facilities must be invented. Never use real patient data.
Never include words: synthetic, training, example, fictional, fake, lorem, ipsum, placeholder.
Wound diagnoses must be clinically plausible with matching ICD-10-CM style codes.
Diabetic or neuropathic ulcers MUST include E11.* AND a site-specific L97.* code.
Venous or arterial ulcers MUST include the vascular family code AND L97.* when ulcer is present.
Pressure injuries MUST use L89.*. Skin tears MUST use S*. Surgical/dehiscence MUST use T81.*.
Do not suggest withdrawn drugs (ranitidine, cisapride, troglitazone, cerivastatin).
"""


def _seed_payload() -> dict[str, Any]:
    if not DATA_PATH.is_file():
        raise FileNotFoundError(f"Missing vocabulary seed file: {DATA_PATH}")
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def _clean_str(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = " ".join(value.split()).strip()
    if len(text) < 2 or LEAK_RE.search(text):
        return None
    return text


def _dedupe_preserve(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _normalize_string_list(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    cleaned: list[str] = []
    for item in raw:
        text = _clean_str(item)
        if text:
            cleaned.append(text)
    return _dedupe_preserve(cleaned)


def _normalize_names(raw: object) -> list[str]:
    return [name for name in _normalize_string_list(raw) if NAME_RE.match(name)]


def _normalize_medications(raw: object) -> list[str]:
    out: list[str] = []
    for item in _normalize_string_list(raw):
        lowered = item.casefold()
        if any(banned in lowered for banned in WITHDRAWN_MEDS):
            continue
        out.append(item)
    return out


def _normalize_diagnoses(raw: object) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw:
        if isinstance(item, dict):
            text = _clean_str(item.get("text"))
            codes_raw = item.get("icd10") or item.get("codes") or []
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            text = _clean_str(item[0])
            codes_raw = item[1]
        else:
            continue
        if not text:
            continue
        if not isinstance(codes_raw, (list, tuple)) or not codes_raw:
            continue
        codes: list[str] = []
        for code in codes_raw:
            if isinstance(code, str) and ICD_RE.match(code.strip().upper()):
                codes.append(code.strip().upper())
        if not codes:
            continue
        text = text if text.endswith(".") else f"{text}."
        if diagnosis_family_errors(text, codes):
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append({"text": text, "icd10": codes})
    return out


def _normalize_cities(raw: object) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        city = _clean_str(item.get("city"))
        state = _clean_str(item.get("state"))
        zipcode = _clean_str(item.get("zip") or item.get("zipcode"))
        if not city or not state or not zipcode:
            continue
        state = state.upper()
        if state != "CA":
            # Keep CA-focused geography for this corpus.
            continue
        if not re.fullmatch(r"\d{5}", zipcode):
            continue
        key = f"{city.casefold()}|{zipcode}"
        if key in seen:
            continue
        seen.add(key)
        out.append({"city": city, "state": state, "zip": zipcode})
    return out


def merge_payload(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    merged["first_names"] = _dedupe_preserve(
        list(base.get("first_names") or []) + _normalize_names(incoming.get("first_names"))
    )
    merged["last_names"] = _dedupe_preserve(
        list(base.get("last_names") or []) + _normalize_names(incoming.get("last_names"))
    )
    for key in (
        "facilities",
        "insurers",
        "note_fragments",
        "service_instructions",
        "service_frequencies",
        "street_names",
    ):
        merged[key] = _dedupe_preserve(
            list(base.get(key) or []) + _normalize_string_list(incoming.get(key))
        )
    merged["medications"] = _dedupe_preserve(
        _normalize_medications(base.get("medications") or [])
        + _normalize_medications(incoming.get("medications"))
    )

    city_base = [
        item
        for item in (base.get("cities") or [])
        if isinstance(item, dict) and item.get("city") and item.get("state") and item.get("zip")
    ]
    cities = city_base + _normalize_cities(incoming.get("cities"))
    seen_cities: set[str] = set()
    unique_cities: list[dict[str, str]] = []
    for item in cities:
        key = f"{str(item['city']).casefold()}|{item['zip']}"
        if key in seen_cities:
            continue
        seen_cities.add(key)
        unique_cities.append(
            {"city": str(item["city"]), "state": str(item["state"]).upper(), "zip": str(item["zip"])}
        )
    merged["cities"] = unique_cities

    diagnoses = [
        item
        for item in (base.get("diagnoses") or [])
        if isinstance(item, dict)
        and not diagnosis_family_errors(str(item.get("text") or ""), [str(c) for c in (item.get("icd10") or [])])
    ]
    diagnoses.extend(_normalize_diagnoses(incoming.get("diagnoses")))
    seen: set[str] = set()
    unique_dx: list[dict[str, Any]] = []
    for item in diagnoses:
        text = _clean_str(item.get("text"))
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        codes = [str(c) for c in (item.get("icd10") or [])]
        if diagnosis_family_errors(text if text.endswith(".") else f"{text}.", codes):
            continue
        unique_dx.append({"text": text if text.endswith(".") else f"{text}.", "icd10": codes})
    merged["diagnoses"] = unique_dx
    return merged


def _request_batch(
    client: Any,
    *,
    model_name: str,
    category: str,
    need: int,
    avoid: list[str],
) -> dict[str, Any]:
    prompts = {
        "first_names": (
            f'Return JSON {{"first_names": [..]}} with {need} diverse given names '
            "used in the US. Title Case only."
        ),
        "last_names": (
            f'Return JSON {{"last_names": [..]}} with {need} diverse family names '
            "used in the US. Title Case only."
        ),
        "facilities": (
            f'Return JSON {{"facilities": [..]}} with {need} invented California '
            "hospital / clinic / home-health / SNF names. No real famous systems."
        ),
        "insurers": (
            f'Return JSON {{"insurers": [..]}} with {need} US health-plan style names.'
        ),
        "medications": (
            f'Return JSON {{"medications": [..]}} with {need} common adult meds as '
            '"Drug dose form" strings. No withdrawn drugs.'
        ),
        "note_fragments": (
            f'Return JSON {{"note_fragments": [..]}} with {need} single-sentence '
            "home-health / wound-care clinical note fragments."
        ),
        "diagnoses": (
            f'Return JSON {{"diagnoses": [{{"text": "...", "icd10": ["E11.621", "L97.412"]}}, ...]}} '
            f"with {need} distinct wound-care diagnoses. Diabetic ulcers MUST include E11.* and L97.*. "
            "Venous/arterial ulcers MUST include vascular code plus L97.*. Pressure injuries use L89.*."
        ),
        "service_instructions": (
            f'Return JSON {{"service_instructions": [..]}} with {need} concise skilled '
            "wound-care order instructions."
        ),
        "service_frequencies": (
            f'Return JSON {{"service_frequencies": [..]}} with {need} visit-frequency phrases.'
        ),
        "street_names": (
            f'Return JSON {{"street_names": [..]}} with {need} Southern California style '
            'street names like "Willow Street" or "Pacific Avenue".'
        ),
        "cities": (
            f'Return JSON {{"cities": [{{"city": "Torrance", "state": "CA", "zip": "90501"}}, ...]}} '
            f"with {need} distinct California cities and real 5-digit ZIP codes in Greater LA / SoCal."
        ),
    }
    avoid_sample = avoid[:40]
    lead = (
        prompts[category]
        + "\nAvoid duplicating these existing values (case-insensitive):\n"
        + json.dumps(avoid_sample, ensure_ascii=True)
    )
    return call_model_for_json(
        client,
        model_name=model_name,
        max_tokens=8192,
        system_prompt=SYSTEM_PROMPT,
        user_content=[],
        lead_text=lead,
    )


def _rewrite_failing_diagnoses(
    client: Any,
    *,
    model_name: str,
    payload: dict[str, Any],
    max_rounds: int,
) -> dict[str, Any]:
    for _round in range(max_rounds):
        bad = failing_diagnoses(payload)
        if not bad:
            return payload
        batch_size = min(25, len(bad))
        sample = bad[:batch_size]
        lead = (
            "Rewrite these wound diagnoses so ICD family rules pass. "
            "Return JSON {\"diagnoses\": [{\"text\": \"...\", \"icd10\": [\"...\"]}]}. "
            "Keep clinical meaning and laterality/site. Replace each item:\n"
            + json.dumps(sample, ensure_ascii=True)
        )
        try:
            batch = call_model_for_json(
                client,
                model_name=model_name,
                max_tokens=8192,
                system_prompt=SYSTEM_PROMPT,
                user_content=[],
                lead_text=lead,
            )
        except AnthropicJsonError as exc:
            raise SystemExit(f"Anthropic diagnosis rewrite failed: {exc}") from exc

        # Drop the failing texts, then merge replacements.
        drop = {str(item.get("text") or "").casefold() for item in sample}
        kept = [
            item
            for item in (payload.get("diagnoses") or [])
            if str(item.get("text") or "").casefold() not in drop
        ]
        payload = merge_payload({**payload, "diagnoses": kept}, batch)
        print(f"diagnoses rewrite: removed {len(sample)}; now {len(payload.get('diagnoses') or [])}", flush=True)
    return payload


def expand_until_targets(
    *,
    model_name: str = DEFAULT_MODEL,
    max_rounds: int = 12,
    cleanup_only: bool = False,
) -> dict[str, Any]:
    load_dotenv()
    client = build_client()
    payload = _seed_payload()
    payload["medications"] = _normalize_medications(payload.get("medications") or [])

    if not payload.get("service_frequencies"):
        payload["service_frequencies"] = [
            "Initial evaluation",
            "Twice weekly",
            "Three times weekly",
            "Weekly",
            "Daily for 5 days",
            "Every other day",
            "One time evaluation",
            "Two times weekly",
            "Monday Wednesday Friday",
            "Biweekly",
            "As needed",
            "Four times weekly",
        ]
    if not payload.get("service_instructions"):
        payload["service_instructions"] = [
            "Assess, measure, photograph, cleanse, and dress wound per physician order.",
            "Evaluate wound etiology and recommend a treatment plan.",
            "Complete wound assessment and coordinate supplies with home-health nursing.",
            "Measure and photograph wound; notify ordering provider of significant change.",
        ]

    # Drop currently invalid diagnoses before growth so floors are honest.
    payload = merge_payload(payload, {})

    if not cleanup_only:
        for category, target in TARGETS.items():
            for _round in range(max_rounds):
                current = payload.get(category) or []
                if len(current) >= target:
                    break
                need = min(50, max(10, target - len(current) + 5))
                if category == "diagnoses":
                    avoid = [item["text"] for item in current if isinstance(item, dict) and "text" in item]
                elif category == "cities":
                    avoid = [f"{item.get('city')} {item.get('zip')}" for item in current if isinstance(item, dict)]
                else:
                    avoid = list(current)
                try:
                    batch = _request_batch(
                        client,
                        model_name=model_name,
                        category=category,
                        need=need,
                        avoid=avoid,
                    )
                except AnthropicJsonError as exc:
                    raise SystemExit(f"Anthropic expansion failed for {category}: {exc}") from exc
                before = len(payload.get(category) or [])
                payload = merge_payload(payload, batch)
                after = len(payload.get(category) or [])
                print(f"{category}: {before} -> {after} (target {target})", flush=True)
                if after <= before:
                    continue
            if len(payload.get(category) or []) < target:
                raise SystemExit(
                    f"Could not reach target for {category}: "
                    f"{len(payload.get(category) or [])}/{target}"
                )

    payload = _rewrite_failing_diagnoses(
        client, model_name=model_name, payload=payload, max_rounds=max_rounds
    )
    # Top up diagnoses if cleanup shrank the bank.
    for _round in range(max_rounds):
        if len(payload.get("diagnoses") or []) >= TARGETS["diagnoses"]:
            break
        need = min(40, TARGETS["diagnoses"] - len(payload.get("diagnoses") or []) + 5)
        avoid = [item["text"] for item in (payload.get("diagnoses") or []) if isinstance(item, dict)]
        batch = _request_batch(
            client,
            model_name=model_name,
            category="diagnoses",
            need=need,
            avoid=avoid,
        )
        before = len(payload.get("diagnoses") or [])
        payload = merge_payload(payload, batch)
        print(f"diagnoses top-up: {before} -> {len(payload.get('diagnoses') or [])}", flush=True)

    payload["diagnoses"] = _cap_icd_tuples(payload.get("diagnoses") or [], max_share=0.029)
    for _round in range(max_rounds):
        failures = validate_vocabulary_payload(payload)
        if not failures:
            break
        avoid = [item["text"] for item in (payload.get("diagnoses") or []) if isinstance(item, dict)]
        batch = _request_batch(
            client,
            model_name=model_name,
            category="diagnoses",
            need=40,
            avoid=avoid,
        )
        payload = merge_payload(payload, batch)
        payload["diagnoses"] = _cap_icd_tuples(payload.get("diagnoses") or [], max_share=0.029)
        print(
            f"diversity pass: diagnoses={len(payload.get('diagnoses') or [])} "
            f"failures={len(validate_vocabulary_payload(payload))}",
            flush=True,
        )

    return payload


def _cap_icd_tuples(diagnoses: list[dict[str, Any]], max_share: float = 0.03) -> list[dict[str, Any]]:
    """Drop over-represented ICD tuples and diagnosis opening bigrams."""

    from .vocab_rules import MAX_DIAGNOSIS_BIGRAM_SHARE

    bi_share = MAX_DIAGNOSIS_BIGRAM_SHARE
    current = list(diagnoses)
    changed = True
    while changed:
        changed = False
        n = len(current)
        max_icd = max(1, int(n * max_share))
        max_bi = max(1, int(n * bi_share))
        icd_counts: Counter[tuple[str, ...]] = Counter()
        bi_counts: Counter[str] = Counter()
        kept: list[dict[str, Any]] = []
        for item in current:
            key = tuple(str(c) for c in (item.get("icd10") or []))
            words = str(item.get("text") or "").split()
            bigram = (
                f"{words[0]} {words[1]}".casefold()
                if len(words) >= 2
                else str(item.get("text") or "").casefold()
            )
            if icd_counts[key] >= max_icd or bi_counts[bigram] >= max_bi:
                changed = True
                continue
            icd_counts[key] += 1
            bi_counts[bigram] += 1
            kept.append(item)
        current = kept
    return current


def write_vocabulary_data(payload: dict[str, Any], path: Path = DATA_PATH) -> Path:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Expand/cleanup synthetic vocabulary banks via Anthropic (offline).")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--output", type=Path, default=DATA_PATH)
    parser.add_argument("--max-rounds", type=int, default=12)
    parser.add_argument(
        "--cleanup-only",
        action="store_true",
        help="Only rewrite failing diagnoses / strip withdrawn meds; do not grow other banks.",
    )
    args = parser.parse_args(argv)
    payload = expand_until_targets(
        model_name=args.model,
        max_rounds=args.max_rounds,
        cleanup_only=args.cleanup_only,
    )
    path = write_vocabulary_data(payload, args.output)
    failures = validate_vocabulary_payload(payload)
    summary = {
        "output": str(path.resolve()),
        "counts": {key: len(payload.get(key) or []) for key in TARGETS},
        "ok": not failures,
        "failure_count": len(failures),
        "failures": failures[:20],
    }
    print(json.dumps(summary, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
