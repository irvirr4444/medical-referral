"""High-volume, reference-informed synthetic referral packet generator.

The local WCW samples informed document families and scan characteristics only.
This module never reads those samples and emits only fabricated patient data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import random
import shutil
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen.canvas import Canvas

from .models import SyntheticReferral, SyntheticService
from .render import render_referral
from .scan import render_scan_variant, scan_profile_names
from .vocabulary import (
    CITIES,
    DIAGNOSES,
    FACILITIES,
    FIRST_NAMES,
    INSURERS,
    LAST_NAMES,
    MEDICATIONS,
    NOTE_FRAGMENTS,
    SERVICE_FREQUENCIES,
    SERVICE_INSTRUCTIONS,
    STREET_NAMES,
)


LOGGER = logging.getLogger(__name__)


LAYOUTS = (
    "patient_chart",
    "wcw_handwritten",
    "hospital_fax",
    "hospital_facesheet",
    "home_health_fax",
    "discharge_packet",
    "agency_summary",
)
FAMILY_DESCRIPTIONS = {
    "patient_chart": "Dense EHR patient chart export with problem list and referral order",
    "wcw_handwritten": "WCW-style handwritten patient referral form",
    "hospital_fax": "Hospital referral transmitted as a multi-page fax packet",
    "hospital_facesheet": "Hospital face sheet followed by encounter and wound-order pages",
    "home_health_fax": "Home-health fax cover, patient summary, and physician order",
    "discharge_packet": "Discharge-planning packet with clinical supporting pages",
    "agency_summary": "Home-health agency episode summary and clinical note",
}
DEFAULT_PROFILES = (*scan_profile_names(), "mixed_fax")
PAGE_RANGES = {
    "patient_chart": (3, 8),
    "wcw_handwritten": (1, 3),
    "hospital_fax": (6, 14),
    "hospital_facesheet": (8, 24),
    "home_health_fax": (3, 8),
    "discharge_packet": (8, 24),
    "agency_summary": (1, 4),
}

SUPPLEMENT_TITLES = (
    "Encounter Summary", "History and Physical", "Wound Assessment", "Medication Profile",
    "Laboratory Results", "Physician Progress Note", "Therapy Evaluation",
    "Discharge Instructions", "Plan of Care", "Clinical Consultation",
)

# Weighted scenario mix for extraction training (sums to 100).
SCENARIO_WEIGHTS: tuple[tuple[str, int], ...] = (
    ("complete", 40),
    ("missing_phone", 10),
    ("missing_address", 10),
    ("missing_insurance", 8),
    ("partial_insurance", 7),
    ("empty_services", 5),
    ("missing_diagnosis", 5),
    ("conflicting_dates", 5),
    ("messy_formats", 5),
    ("multi_wound", 5),
)
SCENARIO_IDS = tuple(name for name, _ in SCENARIO_WEIGHTS)

SCAN_PROFILE_WEIGHTS: tuple[tuple[str, int], ...] = (
    ("native", 25),
    ("office_scan", 20),
    ("fax_clean", 18),
    ("fax_noisy", 15),
    ("photocopy", 10),
    ("low_toner", 7),
    ("mixed_fax", 5),
)


def _pick_scenario(index: int, *, seed: int) -> str:
    rng = random.Random(f"{seed}:scenario:{index}")
    roll = rng.randrange(100)
    cumulative = 0
    for name, weight in SCENARIO_WEIGHTS:
        cumulative += weight
        if roll < cumulative:
            return name
    return SCENARIO_WEIGHTS[-1][0]


def _pick_scan_profile(index: int, *, seed: int, profiles: tuple[str, ...]) -> str:
    allowed = {name for name, _ in SCAN_PROFILE_WEIGHTS}
    chosen = tuple(profile for profile in profiles if profile in allowed) or profiles
    if len(chosen) == 1:
        return chosen[0]
    weights = {name: weight for name, weight in SCAN_PROFILE_WEIGHTS if name in chosen}
    # Any CLI-only profile not in the table gets a small default weight.
    for profile in chosen:
        weights.setdefault(profile, 5)
    rng = random.Random(f"{seed}:profile:{index}")
    names = list(weights)
    total = sum(weights[name] for name in names)
    roll = rng.randrange(total)
    cumulative = 0
    for name in names:
        cumulative += weights[name]
        if roll < cumulative:
            return name
    return names[-1]


def _format_dob(value: date, *, style: int) -> str:
    formats = (
        value.strftime("%m/%d/%Y"),
        value.strftime("%Y-%m-%d"),
        value.strftime("%m-%d-%Y"),
        value.strftime("%m.%d.%Y"),
    )
    return formats[style % len(formats)]


def synthetic_case(index: int, *, seed: int, layout: str | None = None) -> SyntheticReferral:
    rng = random.Random(f"{seed}:case:{index}")
    selected_layout = layout or LAYOUTS[index % len(LAYOUTS)]
    scenario = _pick_scenario(index, seed=seed)
    first, last, middle = _person_identity(index, seed=seed)
    birth = date(1931, 1, 1) + timedelta(days=rng.randrange(18_500))
    referral = date(2026, 1, 1) + timedelta(days=rng.randrange(300))
    diagnosis, codes = rng.choice(DIAGNOSES)
    if rng.random() < 0.72:
        length = rng.uniform(0.4, 9.8)
        width = rng.uniform(0.3, min(7.5, length + 1.7))
        depth = rng.uniform(0.1, 2.6)
        diagnosis = f"{diagnosis.rstrip('.')} measuring {length:.1f} x {width:.1f} x {depth:.1f} cm."
    serial = 10_000_000 + ((seed % 8_000_000) * 100_000) + index
    provider_first, provider_last, _ = _person_identity(index * 7 + 31, seed=seed + 9173)
    provider = f"{provider_first} {provider_last}, {rng.choice(('MD', 'DO', 'DPM', 'NP', 'PA-C', 'RN'))}"
    mrn = _medical_record_number(selected_layout, serial, rng)
    insurance_id, group_number = _coverage_identifiers(serial, rng)
    emergency_first, emergency_last, _ = _person_identity(index * 5 + 13, seed=seed + 4409)

    patient_phone: str | None = _phone(index, seed=seed, style=index % 5)
    patient_address: str | None = _address(index, seed=seed)
    insurance_provider: str | None = rng.choice(INSURERS)
    diagnosis_text: str | None = diagnosis
    icd10_codes = list(codes)
    patient_dob = birth.strftime("%m/%d/%Y")
    admission_date = (referral - timedelta(days=rng.randrange(0, 7))).strftime("%m/%d/%Y")
    referral_date = referral.strftime("%m/%d/%Y")
    requested_services = [
        SyntheticService(
            service="Skilled wound care",
            frequency=rng.choice(SERVICE_FREQUENCIES),
            instructions=rng.choice(SERVICE_INSTRUCTIONS),
        )
    ]
    expected_outcome = "ready_for_human_approval"

    if scenario == "missing_phone":
        patient_phone = None
        expected_outcome = "blocked_missing_threshold"
    elif scenario == "missing_address":
        patient_address = None
        expected_outcome = "blocked_missing_threshold"
    elif scenario == "missing_insurance":
        insurance_provider = None
        insurance_id = None
        group_number = None
        expected_outcome = "manual_review_required"
    elif scenario == "partial_insurance":
        insurance_id = None
        group_number = None
        expected_outcome = "manual_review_required"
    elif scenario == "empty_services":
        requested_services = []
        expected_outcome = "manual_review_required"
    elif scenario == "missing_diagnosis":
        diagnosis_text = None
        icd10_codes = []
        expected_outcome = "manual_review_required"
    elif scenario == "conflicting_dates":
        admission_date = (referral + timedelta(days=1 + rng.randrange(0, 5))).strftime("%m/%d/%Y")
        expected_outcome = "manual_review_required"
    elif scenario == "messy_formats":
        patient_dob = _format_dob(birth, style=1 + (index % 3))
        patient_phone = _phone(index, seed=seed, style=(index + 3) % 5)
        expected_outcome = "ready_for_human_approval"
    elif scenario == "multi_wound":
        second, second_codes = rng.choice(DIAGNOSES)
        while second.casefold() == diagnosis.casefold():
            second, second_codes = rng.choice(DIAGNOSES)
        diagnosis_text = f"{diagnosis.rstrip('.')} Also: {second}"
        merged = list(dict.fromkeys([*codes, *second_codes]))
        icd10_codes = merged
        requested_services = [
            SyntheticService(
                service="Skilled wound care",
                frequency=rng.choice(SERVICE_FREQUENCIES),
                instructions=rng.choice(SERVICE_INSTRUCTIONS),
            ),
            SyntheticService(
                service="Wound Care",
                frequency=rng.choice(SERVICE_FREQUENCIES),
                instructions=rng.choice(SERVICE_INSTRUCTIONS),
            ),
        ]
        expected_outcome = "ready_for_human_approval"

    return SyntheticReferral(
        slug=f"case-{index:09d}",
        layout=selected_layout,
        scenario=scenario,
        scan_style="clean",
        patient_name=f"{last.upper()}, {first.upper()} {middle}",
        patient_dob=patient_dob,
        patient_sex=rng.choice(("Female", "Male")),
        patient_phone=patient_phone,
        patient_address=patient_address,
        patient_mrn=mrn,
        referral_date=referral_date,
        admission_date=admission_date,
        referring_facility=rng.choice(FACILITIES),
        referring_provider_name=provider,
        referring_phone=_phone(index * 3 + 1, seed=seed + 41, style=(index + 2) % 5),
        referring_fax=_phone(index * 3 + 2, seed=seed + 73, style=(index + 4) % 5),
        diagnosis_text=diagnosis_text,
        icd10_codes=icd10_codes,
        insurance_provider=insurance_provider,
        insurance_id=insurance_id,
        insurance_group_number=group_number,
        requested_services=requested_services,
        emergency_contact=(
            f"{emergency_first} {emergency_last} ({rng.choice(('Daughter', 'Son', 'Spouse', 'Caregiver'))}), "
            f"{_phone(index * 5 + 3, seed=seed + 101, style=(index + 1) % 5)}"
        ),
        expected_outcome=expected_outcome,
        expected_monday_duplicate="no_candidates_found",
        expected_drk_duplicate="clear_to_create",
    )


def _person_identity(index: int, *, seed: int) -> tuple[str, str, str]:
    """Create stable names without exhausting a small random-choice bank."""

    population = len(FIRST_NAMES) * len(LAST_NAMES) * 26
    value = (index * 104_729 + seed * 65_537) % population
    first = FIRST_NAMES[value % len(FIRST_NAMES)]
    value //= len(FIRST_NAMES)
    last = LAST_NAMES[value % len(LAST_NAMES)]
    value //= len(LAST_NAMES)
    middle = chr(ord("A") + value % 26)
    return first, last, middle


def _phone(index: int, *, seed: int, style: int) -> str:
    area_codes = (213, 310, 323, 424, 442, 562, 626, 657, 714, 747, 818, 909, 951)
    value = abs(seed * 1_000_003 + index * 7_919)
    area = area_codes[value % len(area_codes)]
    exchange = 200 + (value // len(area_codes)) % 700
    line = (value // (len(area_codes) * 700)) % 10_000
    formats = (
        f"({area}) {exchange:03d}-{line:04d}",
        f"{area}-{exchange:03d}-{line:04d}",
        f"{area}.{exchange:03d}.{line:04d}",
        f"+1 {area} {exchange:03d} {line:04d}",
        f"{area}{exchange:03d}{line:04d}",
    )
    return formats[style % len(formats)]


def _address(index: int, *, seed: int) -> str:
    rng = random.Random(f"{seed}:address:{index}")
    city, state, zipcode = CITIES[(index * 11 + seed) % len(CITIES)]
    number = 101 + ((index * 37 + seed * 13) % 9889)
    unit = ""
    if rng.random() < 0.28:
        unit = f" {rng.choice(('Apt', 'Unit', '#'))} {1 + rng.randrange(399)}"
    return f"{number} {STREET_NAMES[(index * 17 + seed) % len(STREET_NAMES)]}{unit}, {city}, {state} {zipcode}"


def _medical_record_number(layout: str, serial: int, rng: random.Random) -> str:
    value = str(serial)[-10:]
    formats = {
        "patient_chart": (value, f"{value[:3]}-{value[3:6]}-{value[6:]}", f"MR{value[-8:]}"),
        "wcw_handwritten": (value[-7:], f"{value[-3:]} {value[-7:-3]}", f"P{value[-8:]}"),
        "hospital_fax": (f"H{value[-9:]}", value[-9:], f"{value[-4:]}-{value[-9:-4]}"),
        "hospital_facesheet": (f"CSN{value[-8:]}", value, f"{value[:5]} {value[5:]}"),
        "home_health_fax": (f"EPI-{value[-7:]}", value[-8:], f"HH{value[-8:]}"),
        "discharge_packet": (f"FIN{value[-8:]}", value[-9:], f"ACCT-{value[-7:]}"),
        "agency_summary": (f"PAT{value[-8:]}", f"{value[-8:-4]}-{value[-4:]}", value[-8:]),
    }
    return rng.choice(formats[layout])


def _coverage_identifiers(serial: int, rng: random.Random) -> tuple[str, str]:
    value = str(serial)
    member_formats = (
        f"{rng.choice('ABCDEFGHJKLMNPQRSTUVWXYZ')}{value[-8:]}{rng.randrange(10)}",
        f"{value[-3:]}-{value[-5:-3]}-{value[-9:-5]}",
        f"{rng.choice(('H', 'M', 'X', 'R'))}{value[-9:]}",
        f"{value[-4:]} {value[-8:-4]} {rng.randrange(100):02d}",
    )
    group_formats = (
        f"{rng.randrange(10_000, 999_999)}",
        f"GRP{rng.randrange(10_000, 999_999)}",
        f"{rng.choice('ABCDEFGHJKLMNPQRSTUVWXYZ')}{rng.randrange(100_000, 999_999)}",
    )
    return rng.choice(member_formats), rng.choice(group_formats)


def _format_bytes(value: int | None) -> str:
    if value is None:
        return "-"
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    amount = float(value)
    for unit in units:
        if amount < 1024 or unit == units[-1]:
            return f"{amount:.1f} {unit}"
        amount /= 1024
    return f"{amount:.1f} TiB"


def _format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "unknown"
    seconds = max(0, int(round(seconds)))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _format_counts(counts: Counter[str]) -> str:
    return ",".join(f"{name}:{counts[name]}" for name in sorted(counts)) or "none"


def _progress_message(
    *,
    completed: int,
    minimum_count: int,
    total_bytes: int,
    target_bytes: int | None,
    elapsed: float,
    failures: int,
) -> str:
    safe_elapsed = max(elapsed, 0.001)
    documents_per_second = completed / safe_elapsed
    bytes_per_second = total_bytes / safe_elapsed
    remaining_times: list[float] = []
    if completed < minimum_count and documents_per_second > 0:
        remaining_times.append((minimum_count - completed) / documents_per_second)
    if target_bytes is not None and total_bytes < target_bytes and bytes_per_second > 0:
        remaining_times.append((target_bytes - total_bytes) / bytes_per_second)
    eta = max(remaining_times) if remaining_times else 0.0
    size_progress = _format_bytes(total_bytes)
    if target_bytes is not None:
        size_progress = f"{size_progress}/{_format_bytes(target_bytes)}"
    document_progress = (
        f"{completed} PDFs (minimum {minimum_count})"
        if target_bytes is not None
        else f"{completed}/{minimum_count} PDFs"
    )
    return (
        f"{document_progress} | {size_progress} | "
        f"{bytes_per_second / 1_000_000:.2f} MB/s | "
        f"{documents_per_second:.2f} PDFs/s | elapsed {_format_duration(elapsed)} | "
        f"ETA {_format_duration(eta)} | failures {failures}"
    )


def generate_stress_dataset(
    output_dir: str | Path,
    *,
    count: int = 100,
    seed: int = 20260826,
    profiles: tuple[str, ...] = DEFAULT_PROFILES,
    target_bytes: int | None = None,
    workers: int = 4,
    shard_size: int = 1000,
    progress_interval: float = 5.0,
) -> dict[str, Any]:
    """Generate deterministic PDFs until count or target size is reached."""

    if count < 1:
        raise ValueError("count must be positive")
    if workers < 1:
        raise ValueError("workers must be positive")
    if not profiles:
        raise ValueError("at least one scan profile is required")
    if progress_interval < 0:
        raise ValueError("progress_interval cannot be negative")
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    manifest_path = output / "manifest.jsonl"
    failures_path = output / "failures.jsonl"
    dataset_path = output / "dataset.json"

    rows: list[dict[str, Any]] = []
    total_bytes = 0
    candidate_index = 0
    failure_count = 0
    batch_size = max(1, workers * 2)
    started = time.monotonic()
    last_progress = started
    layout_counts: Counter[str] = Counter()
    profile_counts: Counter[str] = Counter()
    LOGGER.info(
        "Starting PDF generation: minimum=%d PDFs, target=%s, workers=%d, output=%s",
        count,
        _format_bytes(target_bytes) if target_bytes is not None else "not set",
        workers,
        output.resolve(),
    )
    with (
        manifest_path.open("w", encoding="utf-8") as manifest,
        failures_path.open("w", encoding="utf-8") as failures,
        ProcessPoolExecutor(max_workers=workers) as pool,
    ):
        while len(rows) < count or (target_bytes is not None and total_bytes < target_bytes):
            remaining_documents = max(0, count - len(rows))
            take = min(batch_size, remaining_documents) if remaining_documents else batch_size
            indexes = list(range(candidate_index, candidate_index + max(1, take)))
            candidate_index += len(indexes)
            futures = {
                pool.submit(_generate_one, output, item, seed, profiles, shard_size): item
                for item in indexes
            }
            batch_rows: dict[int, dict[str, Any]] = {}
            for future in as_completed(futures):
                item = futures[future]
                try:
                    row = future.result()
                except Exception as exc:
                    failure_count += 1
                    failure = {
                        "case_index": item,
                        "layout": LAYOUTS[item % len(LAYOUTS)],
                        "scan_profile": profiles[item % len(profiles)],
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                    failures.write(json.dumps(failure, sort_keys=True) + "\n")
                    failures.flush()
                    LOGGER.error(
                        "Failed case %d (%s/%s): %s: %s",
                        item,
                        failure["layout"],
                        failure["scan_profile"],
                        failure["error_type"],
                        failure["error"],
                    )
                else:
                    batch_rows[item] = row
                    total_bytes += int(row["size_bytes"])
                    layout_counts[row["layout"]] += 1
                    profile_counts[row["scan_profile"]] += 1

                now = time.monotonic()
                if progress_interval == 0 or now - last_progress >= progress_interval:
                    LOGGER.info(
                        _progress_message(
                            completed=len(rows) + len(batch_rows),
                            minimum_count=count,
                            total_bytes=total_bytes,
                            target_bytes=target_bytes,
                            elapsed=now - started,
                            failures=failure_count,
                        )
                    )
                    last_progress = now

            if not batch_rows:
                raise RuntimeError(
                    f"all {len(indexes)} documents in the latest batch failed; "
                    f"see {failures_path}"
                )
            for item in sorted(batch_rows):
                row = batch_rows[item]
                manifest.write(json.dumps(row, sort_keys=True) + "\n")
                rows.append(row)
            manifest.flush()

    elapsed = time.monotonic() - started
    LOGGER.info(
        "%s | layouts=%s | profiles=%s",
        _progress_message(
            completed=len(rows),
            minimum_count=count,
            total_bytes=total_bytes,
            target_bytes=target_bytes,
            elapsed=elapsed,
            failures=failure_count,
        ),
        _format_counts(layout_counts),
        _format_counts(profile_counts),
    )

    summary = {
        "version": 1,
        "synthetic_only": True,
        "seed": seed,
        "document_count": len(rows),
        "total_bytes": total_bytes,
        "elapsed_seconds": round(elapsed, 3),
        "average_megabytes_per_second": round(total_bytes / max(elapsed, 0.001) / 1_000_000, 3),
        "failure_count": failure_count,
        "profiles": list(profiles),
        "layouts": list(LAYOUTS),
        "family_descriptions": FAMILY_DESCRIPTIONS,
        "diversity": _diversity_summary(rows),
        "manifest": manifest_path.name,
        "failures": failures_path.name,
    }
    dataset_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return {**summary, "output_dir": str(output.resolve()), "dataset": str(dataset_path.resolve())}


def _generate_one(
    output: Path,
    index: int,
    seed: int,
    profiles: tuple[str, ...],
    shard_size: int,
) -> dict[str, Any]:
    case = synthetic_case(index, seed=seed)
    profile = _pick_scan_profile(index, seed=seed, profiles=profiles)
    rng = random.Random(f"{seed}:pages:{index}")
    page_min, page_max = PAGE_RANGES[case.layout]
    target_pages = rng.randint(page_min, page_max)
    shard = output / "pdfs" / f"shard-{index // shard_size:05d}"
    shard.mkdir(parents=True, exist_ok=True)
    filename = f"referral-{case.slug}-{case.layout}-{profile}.pdf"
    destination = shard / filename
    layout_variant = int(hashlib.sha256(f"{seed}:{index}:layout".encode()).hexdigest()[:8], 16) % 6

    with TemporaryDirectory(prefix="wcw-synthetic-") as temporary:
        temporary_dir = Path(temporary)
        base = render_referral(case, temporary_dir / "base.pdf", variant=layout_variant)
        expanded = temporary_dir / "expanded.pdf"
        _expand_packet(base, expanded, case=case, target_pages=target_pages, seed=f"{seed}:{index}")
        render_scan_variant(expanded, destination, profile=profile, seed=f"{seed}:{index}:{profile}")

    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    page_count = len(PdfReader(str(destination)).pages)
    relative = destination.relative_to(output).as_posix()
    return {
        "document_id": case.slug,
        "filename": filename,
        "path": relative,
        "sha256": digest,
        "size_bytes": destination.stat().st_size,
        "page_count": page_count,
        "layout": case.layout,
        "layout_variant": layout_variant,
        "scan_profile": profile,
        "scenario": case.scenario,
        "expected_outcome": case.expected_outcome,
        "text_layer_expected": profile == "native",
        "synthetic_only": True,
        "gold": case.gold_record(filename),
        "phi_values": {
            "patient_name": case.patient_name,
            "date_of_birth": case.patient_dob,
            "phone": case.patient_phone,
            "address": case.patient_address,
            "medical_record_number": case.patient_mrn,
            "insurance_id": case.insurance_id,
            "emergency_contact": case.emergency_contact,
        },
    }


def _diversity_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    fields = (
        "patient_name",
        "date_of_birth",
        "phone",
        "address",
        "medical_record_number",
        "insurance_id",
    )
    unique = {
        field: len({row["phi_values"].get(field) for row in rows})
        for field in fields
    }
    layouts = {layout: 0 for layout in LAYOUTS}
    profiles = {profile: 0 for profile in DEFAULT_PROFILES}
    scenarios = {name: 0 for name in SCENARIO_IDS}
    for row in rows:
        layouts[row["layout"]] = layouts.get(row["layout"], 0) + 1
        profiles[row["scan_profile"]] = profiles.get(row["scan_profile"], 0) + 1
        scenario = row.get("scenario") or "complete"
        scenarios[scenario] = scenarios.get(scenario, 0) + 1
    return {
        "unique_values": unique,
        "uniqueness_ratio": {
            field: round(count / len(rows), 6) if rows else 0.0
            for field, count in unique.items()
        },
        "layout_counts": layouts,
        "scan_profile_counts": profiles,
        "scenario_counts": scenarios,
    }


def _expand_packet(
    source: Path,
    output: Path,
    *,
    case: SyntheticReferral,
    target_pages: int,
    seed: str,
) -> None:
    reader = PdfReader(str(source))
    if len(reader.pages) >= target_pages:
        shutil.copyfile(source, output)
        return
    supplemental = output.with_suffix(".supplemental.pdf")
    _render_supplemental_pages(
        supplemental,
        case=case,
        start_page=len(reader.pages) + 1,
        total_pages=target_pages,
        seed=seed,
    )
    combined = output.with_suffix(".combined.pdf")
    writer = PdfWriter()
    writer.append(str(source))
    writer.append(str(supplemental))
    with combined.open("wb") as stream:
        writer.write(stream)
    _stamp_packet_headers(combined, output, case=case, total_pages=target_pages)


def _stamp_packet_headers(
    source: Path,
    output: Path,
    *,
    case: SyntheticReferral,
    total_pages: int,
) -> None:
    """Normalize fax page numbering after a packet has been expanded."""

    overlay = output.with_suffix(".headers.pdf")
    canvas = Canvas(str(overlay), pagesize=letter, pageCompression=1)
    for page_number in range(1, total_pages + 1):
        canvas.setFillColor(colors.white)
        canvas.rect(0, 764, letter[0], 28, fill=1, stroke=0)
        canvas.setFillColor(colors.HexColor("#444444"))
        canvas.setFont("Courier", 6.5)
        canvas.drawString(28, 776, f"FROM {case.referring_facility.upper()[:42]}")
        canvas.drawCentredString(letter[0] / 2, 776, f"PAGE {page_number:02d} OF {total_pages:02d}")
        canvas.drawRightString(584, 776, f"FAX {case.referring_fax}")
        if page_number == 1 and case.layout in {"hospital_fax", "discharge_packet"}:
            canvas.setFillColor(colors.white)
            canvas.rect(184, 448, 110, 45, fill=1, stroke=0)
            canvas.setFillColor(colors.black)
            canvas.setFont("Helvetica", 10)
            canvas.drawString(190, 470, str(total_pages))
        canvas.showPage()
    canvas.save()

    source_reader = PdfReader(str(source))
    overlay_reader = PdfReader(str(overlay))
    writer = PdfWriter()
    for page, header in zip(source_reader.pages, overlay_reader.pages):
        page.merge_page(header, over=True)
        writer.add_page(page)
    with output.open("wb") as stream:
        writer.write(stream)


def _render_supplemental_pages(
    path: Path,
    *,
    case: SyntheticReferral,
    start_page: int,
    total_pages: int,
    seed: str,
) -> None:
    rng = random.Random(seed)
    canvas = Canvas(str(path), pagesize=letter, pageCompression=1)
    for page_number in range(start_page, total_pages + 1):
        title = SUPPLEMENT_TITLES[(page_number + rng.randrange(len(SUPPLEMENT_TITLES))) % len(SUPPLEMENT_TITLES)]
        _supplemental_header(canvas, case, title, page_number, total_pages)
        if title in {"Medication Profile", "Laboratory Results"}:
            _dense_table(canvas, case, title, rng)
        else:
            _dense_note(canvas, case, title, rng)
        canvas.setFont("Helvetica", 6)
        canvas.setFillColor(colors.HexColor("#555555"))
        canvas.drawCentredString(letter[0] / 2, 15, "CONFIDENTIAL - PATIENT HEALTH INFORMATION")
        canvas.showPage()
    canvas.save()


def _supplemental_header(
    canvas: Canvas,
    case: SyntheticReferral,
    title: str,
    page_number: int,
    total_pages: int,
) -> None:
    canvas.setFillColor(colors.black)
    canvas.setFont("Courier", 7)
    canvas.drawString(28, 775, f"FROM {case.referring_facility.upper()}  PAGE {page_number:02d} OF {total_pages:02d}")
    canvas.drawRightString(584, 775, f"FAX {case.referring_fax}")
    canvas.setFont("Helvetica-Bold", 13)
    canvas.drawString(42, 742, case.referring_facility.upper())
    canvas.setFont("Helvetica-Bold", 11)
    canvas.drawString(42, 719, title.upper())
    canvas.setFont("Helvetica", 8)
    canvas.drawString(42, 701, f"Patient: {case.patient_name}    DOB: {case.patient_dob}    MRN: {case.patient_mrn}")
    canvas.line(42, 693, 570, 693)


def _dense_table(canvas: Canvas, case: SyntheticReferral, title: str, rng: random.Random) -> None:
    y = 670
    headers = ("Date", "Code / Medication", "Result / Dose", "Reference / Instructions", "Status")
    widths = (62, 132, 95, 170, 65)
    x = 42
    canvas.setFillColor(colors.HexColor("#202020"))
    canvas.rect(x, y - 15, sum(widths), 19, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 6.5)
    for header, width in zip(headers, widths):
        canvas.drawString(x + 3, y - 9, header)
        x += width
    canvas.setFillColor(colors.black)
    rows = 22 if title == "Medication Profile" else 27
    if title == "Medication Profile":
        values = MEDICATIONS
        results = ("1 tablet", "2 tablets", "5 units", "10 units", "As directed")
        instructions = ("Once daily", "Twice daily", "At bedtime", "With meals", "As needed")
        statuses = ("Current", "Active", "Continued", "Discontinued")
    else:
        values = ("WBC", "Hemoglobin", "Hematocrit", "Creatinine", "Glucose", "Albumin", "Sodium", "Potassium")
        results = ("7.8 K/uL", "11.4 g/dL", "35.2 %", "1.1 mg/dL", "112 mg/dL", "3.4 g/dL", "138 mmol/L", "4.2 mmol/L")
        instructions = ("Within reference range", "Low", "High", "Review at follow-up", "Repeat as ordered")
        statuses = ("Final", "Reviewed", "Corrected")
    for row in range(rows):
        row_y = y - 34 - row * 22
        if row_y < 55:
            break
        if row % 2:
            canvas.setFillColor(colors.HexColor("#F1F1F1"))
            canvas.rect(42, row_y - 5, sum(widths), 21, fill=1, stroke=0)
        canvas.setFillColor(colors.black)
        canvas.setFont("Helvetica", 6.5)
        fields = (
            f"08/{1 + row % 27:02d}/26",
            rng.choice(values),
            rng.choice(results),
            rng.choice(instructions),
            rng.choice(statuses),
        )
        x = 42
        for value, width in zip(fields, widths):
            canvas.drawString(x + 3, row_y + 2, str(value)[:32])
            canvas.rect(x, row_y - 5, width, 21, fill=0, stroke=1)
            x += width


def _dense_note(canvas: Canvas, case: SyntheticReferral, title: str, rng: random.Random) -> None:
    y = 670
    sections = (
        "Reason for consultation", "History of present illness", "Wound assessment",
        "Review of systems", "Physical examination", "Assessment and plan",
        "Orders and follow-up",
    )
    sentences = (
        f"Patient referred for {case.diagnosis_text}",
        *NOTE_FRAGMENTS,
        f"Emergency contact on file: {case.emergency_contact}.",
    )
    for section in sections:
        if y < 90:
            break
        canvas.setFont("Helvetica-Bold", 8)
        canvas.drawString(44, y, section.upper())
        y -= 14
        font_size = rng.choice((7, 7, 8))
        canvas.setFont("Helvetica", font_size)
        paragraph = " ".join(rng.sample(sentences, k=rng.randint(3, 5)))
        words = paragraph.split()
        line: list[str] = []
        for word in words:
            candidate = " ".join((*line, word))
            if canvas.stringWidth(candidate, "Helvetica", font_size) > 505:
                canvas.drawString(48, y, " ".join(line))
                y -= 10
                line = [word]
            else:
                line.append(word)
        if line:
            canvas.drawString(48, y, " ".join(line))
            y -= 10
        y -= rng.randint(8, 17)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate high-fidelity synthetic PDFs for deidentification stress tests.")
    parser.add_argument("--output-dir", type=Path, default=Path("output/pdf/deid-stress"))
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--target-gb", type=float)
    parser.add_argument("--seed", type=int, default=20260826)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--shard-size", type=int, default=1000)
    parser.add_argument("--profiles", default=",".join(DEFAULT_PROFILES))
    parser.add_argument("--progress-seconds", type=float, default=5.0)
    parser.add_argument("--quiet", action="store_true", help="Suppress progress logs; final JSON is still printed.")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )
    profiles = tuple(value.strip() for value in args.profiles.split(",") if value.strip())
    result = generate_stress_dataset(
        args.output_dir,
        count=args.count,
        seed=args.seed,
        profiles=profiles,
        target_bytes=int(args.target_gb * 1024**3) if args.target_gb else None,
        workers=args.workers,
        shard_size=args.shard_size,
        progress_interval=args.progress_seconds,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
