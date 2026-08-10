from __future__ import annotations

import json
from pathlib import Path

from intake_extractor.canonical_referral import CanonicalReferral


FIXTURE = Path("eval/fixtures/butler-canonical-referral.json")
GOLD = Path("eval/gold/BUTLER_ALVA_demo.gold.json")


def test_butler_canonical_fixture_validates() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    record = CanonicalReferral.model_validate(payload)

    assert record.patient.name.full == "BUTLER, ALVA"
    assert record.patient.date_of_birth == "1940-10-04"
    assert record.patient.mrn is None
    assert record.patient.source_patient_id == "6227"
    assert len(record.insurances) == 2
    assert record.insurances[0].payer_name == "MEDICARE PART B"
    assert record.field_quality["home_health_or_hospice"].status == "missing"


def test_butler_fixture_preserves_reviewed_gold_identity() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    gold = json.loads(GOLD.read_text(encoding="utf-8"))["record"]
    record = CanonicalReferral.model_validate(payload)

    assert record.patient.phones[0].number == gold["patient_phone"]
    assert record.patient.source_patient_id == gold["patient_mrn"]
    assert record.patient.mrn is None
    assert record.insurances[0].policy_number == gold["insurance_id"]
    assert len(record.clinical.diagnoses) == len(gold["icd10_codes"])
