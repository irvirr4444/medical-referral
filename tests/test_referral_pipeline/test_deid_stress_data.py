from __future__ import annotations

import json
import logging
from pathlib import Path

import pdfplumber

from referral_pipeline.synthetic_data.stress import generate_stress_dataset, synthetic_case


def test_synthetic_case_is_deterministic_and_reference_independent() -> None:
    first = synthetic_case(7, seed=1234)
    second = synthetic_case(7, seed=1234)
    assert first == second
    assert "SYN" not in first.patient_mrn
    assert "555" not in (first.patient_phone or "")
    assert first.slug == "case-000000007"


def test_large_case_sample_has_unique_core_identifiers_and_no_visible_shortcuts() -> None:
    cases = [synthetic_case(index, seed=20260826) for index in range(2_000)]
    assert len({case.patient_name for case in cases}) == len(cases)
    assert len({case.patient_mrn for case in cases}) == len(cases)
    assert len({case.patient_phone for case in cases}) == len(cases)
    assert len({case.patient_address for case in cases}) == len(cases)
    rendered_values = " ".join(
        f"{case.patient_name} {case.patient_mrn} {case.patient_phone} {case.patient_address}"
        for case in cases
    ).lower()
    assert "synthetic" not in rendered_values
    assert "training" not in rendered_values
    assert "example" not in rendered_values


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
    assert rows[0]["scan_profile"] == "native"
    assert rows[1]["scan_profile"] == "fax_noisy"
    assert rows[0]["phi_values"]["patient_name"]
    assert rows[0]["sha256"] != rows[1]["sha256"]
    for row in rows:
        path = tmp_path / "stress" / row["path"]
        assert path.read_bytes().startswith(b"%PDF-")
        assert row["page_count"] >= 1
        with pdfplumber.open(path) as document:
            text = "".join(page.extract_text() or "" for page in document.pages)
        if row["text_layer_expected"]:
            assert row["phi_values"]["patient_name"] in text
            assert "synthetic" not in text.lower()
            assert "not a real patient" not in text.lower()
        else:
            assert text == ""
