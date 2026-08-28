from __future__ import annotations

import json
from pathlib import Path

from referral_pipeline.synthetic_data.generate import generate_dataset
from referral_pipeline.synthetic_data.records import SYNTHETIC_CASES


def test_synthetic_records_cover_each_layout_twice() -> None:
    counts: dict[str, int] = {}
    for case in SYNTHETIC_CASES:
        counts[case.layout] = counts.get(case.layout, 0) + 1

    assert len(SYNTHETIC_CASES) == 14
    assert set(counts.values()) == {2}
    assert all("555" in case.referring_phone for case in SYNTHETIC_CASES)
    assert len({case.patient_mrn for case in SYNTHETIC_CASES}) == 14


def test_generator_writes_pdf_gold_and_hash_manifest(tmp_path: Path) -> None:
    result = generate_dataset(tmp_path / "dataset")
    dataset = json.loads(Path(result["dataset"]).read_text(encoding="utf-8"))

    assert result["pdf_count"] == 14
    assert len(dataset["cases"]) == 14
    for item in dataset["cases"]:
        pdf = tmp_path / "dataset" / "pdfs" / item["filename"]
        gold = tmp_path / "dataset" / item["gold_file"]
        metadata = tmp_path / "dataset" / item["metadata_file"]
        assert pdf.read_bytes().startswith(b"%PDF-")
        assert gold.is_file()
        assert metadata.is_file()
        metadata_payload = json.loads(metadata.read_text(encoding="utf-8"))
        assert metadata_payload["pdf_filename"] == pdf.name
        assert metadata_payload["source_pages"]
        assert next(
            entity["value"]
            for entity in metadata_payload["entities"]
            if entity["type"] == "PATIENT_NAME"
        ) == item["patient_name"]
        assert len(item["sha256"]) == 64
