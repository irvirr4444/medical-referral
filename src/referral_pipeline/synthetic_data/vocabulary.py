"""Large, deterministic vocabularies for realistic fictitious referral data.

Values live in vocabulary_data.json (expanded offline). They are assembled for
synthetic packets only and must never be used to contact a person or make a care
decision.
"""

from __future__ import annotations

import json
from pathlib import Path


def _load() -> dict:
    path = Path(__file__).with_name("vocabulary_data.json")
    return json.loads(path.read_text(encoding="utf-8"))


_DATA = _load()

FIRST_NAMES = tuple(_DATA["first_names"])
LAST_NAMES = tuple(_DATA["last_names"])
STREET_NAMES = tuple(_DATA["street_names"])
CITIES = tuple((item["city"], item["state"], item["zip"]) for item in _DATA["cities"])
FACILITIES = tuple(_DATA["facilities"])
INSURERS = tuple(_DATA["insurers"])
DIAGNOSES = tuple((item["text"], tuple(item["icd10"])) for item in _DATA["diagnoses"])
NOTE_FRAGMENTS = tuple(_DATA["note_fragments"])
MEDICATIONS = tuple(_DATA["medications"])
SERVICE_INSTRUCTIONS = tuple(_DATA["service_instructions"])
SERVICE_FREQUENCIES = tuple(_DATA["service_frequencies"])
