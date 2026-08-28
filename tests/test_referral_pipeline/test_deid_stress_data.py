from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

import pdfplumber

from referral_pipeline.synthetic_data import vocabulary
from referral_pipeline.synthetic_data.models import _parse_flexible_date
from referral_pipeline.synthetic_data.render import render_referral
from referral_pipeline.synthetic_data.stress import (
    SCENARIO_IDS,
    generate_stress_dataset,
    synthetic_case,
)
from referral_pipeline.synthetic_data.vocab_rules import (
    SIZE_FLOORS,
    load_vocabulary_data,
    validate_vocabulary_payload,
)


def test_vocabulary_banks_meet_quality_gate() -> None:
    payload = load_vocabulary_data()
    failures = validate_vocabulary_payload(payload)
    assert failures == []
    assert len(vocabulary.FIRST_NAMES) >= SIZE_FLOORS["first_names"]
    assert len(vocabulary.LAST_NAMES) >= SIZE_FLOORS["last_names"]
    assert len(vocabulary.CITIES) >= SIZE_FLOORS["cities"]
    assert len(vocabulary.STREET_NAMES) >= SIZE_FLOORS["street_names"]
    assert len(vocabulary.DIAGNOSES) >= SIZE_FLOORS["diagnoses"]
    assert all("ranitidine" not in med.casefold() for med in vocabulary.MEDICATIONS)


def test_synthetic_case_is_deterministic_and_reference_independent() -> None:
    first = synthetic_case(7, seed=1234)
    second = synthetic_case(7, seed=1234)
    assert first == second
    assert "SYN" not in first.patient_mrn
    if first.patient_phone:
        assert "555" not in first.patient_phone
    assert first.slug == "case-000000007"
    assert first.scenario in SCENARIO_IDS


def test_large_case_sample_has_unique_core_identifiers_and_scenario_mix() -> None:
    cases = [synthetic_case(index, seed=20260826) for index in range(2_000)]
    assert len({case.patient_name for case in cases}) == len(cases)
    assert len({case.patient_mrn for case in cases}) == len(cases)

    phones = [case.patient_phone for case in cases if case.patient_phone]
    addresses = [case.patient_address for case in cases if case.patient_address]
    assert phones and len(phones) == len(set(phones))
    assert addresses and len(addresses) == len(set(addresses))
    assert len(phones) < len(cases)
    assert len(addresses) < len(cases)

    scenarios = {case.scenario for case in cases}
    assert scenarios == set(SCENARIO_IDS)

    for case in cases:
        if case.scenario == "missing_phone":
            assert case.patient_phone is None
            assert case.expected_outcome == "blocked_missing_threshold"
        elif case.scenario == "missing_address":
            assert case.patient_address is None
            assert case.expected_outcome == "blocked_missing_threshold"
        elif case.scenario == "missing_insurance":
            assert case.insurance_provider is None
            assert case.insurance_id is None
            assert case.expected_outcome == "manual_review_required"
        elif case.scenario == "partial_insurance":
            assert case.insurance_provider
            assert case.insurance_id is None
            assert case.insurance_group_number is None
            assert case.expected_outcome == "manual_review_required"
        elif case.scenario == "empty_services":
            assert case.requested_services == []
            assert case.expected_outcome == "manual_review_required"
        elif case.scenario == "missing_diagnosis":
            assert case.diagnosis_text is None
            assert case.icd10_codes == []
            assert case.expected_outcome == "manual_review_required"
        elif case.scenario == "conflicting_dates":
            assert case.admission_date
            assert _parse_flexible_date(case.admission_date) > _parse_flexible_date(case.referral_date)
            assert case.expected_outcome == "manual_review_required"
        elif case.scenario == "messy_formats":
            # Drawn DOB uses an alternate shape (not canonical MM/DD/YYYY).
            assert case.patient_dob.count("/") != 2
            gold = case.gold_record("x.pdf")
            assert gold["patient_dob"] == case.patient_dob
            assert gold["patient_phone"] == case.patient_phone
            assert case.expected_outcome == "ready_for_human_approval"
        elif case.scenario == "multi_wound":
            assert case.diagnosis_text and "Also:" in case.diagnosis_text
            assert len(case.icd10_codes) >= 2
            assert len(case.requested_services) == 2
            assert case.expected_outcome == "ready_for_human_approval"
        else:
            assert case.scenario == "complete"
            assert case.patient_phone and case.patient_address
            assert case.expected_outcome == "ready_for_human_approval"

    rendered_values = " ".join(
        f"{case.patient_name} {case.patient_mrn} {case.patient_phone or ''} {case.patient_address or ''}"
        for case in cases
    ).lower()
    assert "synthetic" not in rendered_values
    assert "training" not in rendered_values
    assert "example" not in rendered_values


def test_layout_variant_changes_pdf_bytes_but_not_gold_fields(tmp_path: Path) -> None:
    case = synthetic_case(3, seed=99)
    # Force a layout that uses margin/column jitter.
    case = case.model_copy(update={"layout": "patient_chart", "scenario": "complete"})
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    render_referral(case, a, variant=0)
    render_referral(case, b, variant=1)
    assert hashlib.sha256(a.read_bytes()).hexdigest() != hashlib.sha256(b.read_bytes()).hexdigest()
    assert case.gold_record("a.pdf")["patient_name"] == case.gold_record("b.pdf")["patient_name"]
    assert case.gold_record("a.pdf")["patient_dob"] == case.gold_record("b.pdf")["patient_dob"]


def test_stress_generator_writes_native_and_image_only_gold(tmp_path: Path, caplog) -> None:
    caplog.set_level(logging.INFO, logger="referral_pipeline.synthetic_data.stress")
    result = generate_stress_dataset(
        tmp_path / "stress",
        count=2,
        seed=99,
        profiles=("native", "fax_noisy"),
        workers=2,
        progress_interval=0,
    )
    rows = [json.loads(line) for line in (tmp_path / "stress" / "manifest.jsonl").read_text().splitlines()]
    assert result["document_count"] == 2
    assert result["failure_count"] == 0
    assert result["elapsed_seconds"] > 0
    assert len(rows) == 2
    assert (tmp_path / "stress" / "failures.jsonl").read_text() == ""
    assert "2/2 PDFs" in caplog.text
    assert "ETA 00:00:00" in caplog.text
    assert rows[0]["phi_values"]["patient_name"]
    assert rows[0]["scenario"] in SCENARIO_IDS
    assert set(result["diversity"]["scenario_counts"]) >= set(SCENARIO_IDS)
    assert rows[0]["sha256"] != rows[1]["sha256"]
    for row in rows:
        path = tmp_path / "stress" / row["path"]
        metadata_path = tmp_path / "stress" / row["metadata_path"]
        assert path.read_bytes().startswith(b"%PDF-")
        assert metadata_path.is_file()
        assert hashlib.sha256(metadata_path.read_bytes()).hexdigest() == row["metadata_sha256"]
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        assert set(metadata) == {
            "schema_version",
            "document_id",
            "pdf_filename",
            "source_pages",
            "entities",
        }
        assert metadata["schema_version"] == "1.0"
        assert metadata["pdf_filename"] == path.name
        assert len(metadata["source_pages"]) == row["page_count"]
        name_entity = next(entity for entity in metadata["entities"] if entity["type"] == "PATIENT_NAME")
        assert name_entity["value"] == row["phi_values"]["patient_name"]
        assert name_entity["occurrences"]
        pages = {page["page"]: page["text"] for page in metadata["source_pages"]}
        for entity in metadata["entities"]:
            for occurrence in entity["occurrences"]:
                page_text = pages[occurrence["page"]]
                assert page_text[occurrence["char_start"] : occurrence["char_end"]] == entity["value"]
        assert row["page_count"] >= 1
        gold = row["gold"]
        assert gold["patient_phone"] == row["phi_values"]["phone"]
        assert gold["patient_address"] == row["phi_values"]["address"]
        with pdfplumber.open(path) as document:
            text = "".join(page.extract_text() or "" for page in document.pages)
        if row["text_layer_expected"]:
            assert row["phi_values"]["patient_name"] in text
            assert "synthetic" not in text.lower()
            assert "not a real patient" not in text.lower()
            if row["phi_values"]["phone"] is None or row["phi_values"]["address"] is None:
                assert "Not provided" in text
        else:
            assert text == ""
