"""De-identify the sidecar JSONs of a patient bundle with the same crosswalk
used for the PDFs, so PDFs and JSONs stay mutually consistent.

The caller (deidentify_patient_docs.py) supplies closures over its per-patient
state: `scrub` (full known-map + name-regex + generic-pattern string scrubber),
`fake_id` (format-preserving surrogate factory) and the record-id map. This
module only knows how to walk JSON payloads and handle JSON-specific leaks:

  - ISO timestamps: the date part shifts with the bundle offset (the scrubber's
    generic ISO-date pattern already does this); time-of-day is kept.
  - Windows paths: the OS username segment is anonymized, and file names inside
    paths get the same fake record IDs as the renamed PDFs.
  - sha256 fields: dropped (they fingerprint the original PHI-bearing bytes).
  - integer IDs: replaced when their string form is a known identifier, plus
    board/user-id keys that tie records to real people.
  - *.metadata.json: entity values become their surrogates and the char-offset
    occurrences are recomputed against the scrubbed page text.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable

WIN_USER_RX = re.compile(r"(?i)([A-Z]:\\+Users\\+)[^\\]+")
BASE64ISH_RX = re.compile(r"^[A-Za-z0-9+/=\s]{4000,}$")
DROP_KEYS = {"sha256"}
INT_ID_KEYS = {"item_id", "actor_user_id", "id"}  # "id" only inside personsAndTeams


INT_KEY_RX = re.compile(r"(?i)^(?:patient_?id|item_id|actor_user_id)$")


class JsonDeidentifier:
    def __init__(self, *, scrub: Callable[[str], str], fake_id: Callable[[str], str],
                 id_map: dict[str, str], slug_pair: tuple[str, str],
                 known_ids: set[str], sanitize_text: Callable[[str], str],
                 age_jitter: int = 0):
        self.age_jitter = age_jitter
        self.scrub = scrub
        self.fake_id = fake_id
        self.id_map = id_map
        self.real_slug, self.fake_slug = slug_pair
        self.known_ids = known_ids  # digit-only known identifier values
        self.sanitize_text = sanitize_text  # names+ids+dates in filename shapes
        self.flags: list[str] = []

    # -- string / int handling -------------------------------------------------

    def _clean_string(self, s: str) -> str:
        out = WIN_USER_RX.sub(r"\1user", s)
        if self.real_slug:
            out = re.sub(re.escape(self.real_slug), self.fake_slug, out,
                         flags=re.IGNORECASE)
        for real, fake in self.id_map.items():
            out = re.sub(rf"(?<!\d){re.escape(real)}(?!\d)", fake, out)
        out = self.sanitize_text(out)  # Butler_Alva / 20260723-style path segments
        if BASE64ISH_RX.match(out):
            self.flags.append("opaque base64-like blob scrubbed as text - review")
        return self.scrub(out)

    def _clean_int(self, key: str, v: int, in_people: bool) -> int:
        if key.lower() == "age" and 0 < v < 120:
            return 90 if v + self.age_jitter >= 90 or v >= 90 else max(v + self.age_jitter, 1)
        replace = (str(abs(v)) in self.id_map
                   or str(abs(v)) in self.known_ids
                   or INT_KEY_RX.match(key)
                   or (key == "id" and in_people))
        if not replace:
            return v
        fake = self.fake_id(str(abs(v)))
        return -int(fake) if v < 0 else int(fake)

    # -- recursive walk ----------------------------------------------------------

    def walk(self, obj, key: str = "", in_people: bool = False):
        if isinstance(obj, dict):
            return {k: self.walk(v, k, in_people or k == "personsAndTeams")
                    for k, v in obj.items() if k not in DROP_KEYS}
        if isinstance(obj, list):
            return [self.walk(v, key, in_people) for v in obj]
        if isinstance(obj, str):
            return self._clean_string(obj)
        if isinstance(obj, bool):
            return obj
        if isinstance(obj, int):
            return self._clean_int(key, obj, in_people)
        return obj

    # -- metadata.json entity offsets -------------------------------------------

    def fix_metadata_offsets(self, data: dict) -> None:
        pages = {p.get("page"): p.get("text", "")
                 for p in data.get("source_pages", []) if isinstance(p, dict)}
        for ent in data.get("entities", []):
            value = ent.get("value", "")
            occurrences = []
            if value:
                needle = value.lower()
                for page_no, text in pages.items():
                    low = text.lower()
                    start = low.find(needle)
                    while start != -1:
                        occurrences.append({"page": page_no, "char_start": start,
                                            "char_end": start + len(value)})
                        start = low.find(needle, start + 1)
            ent["occurrences"] = occurrences


def deidentify_jsons(folder: Path, out_dir: Path, *,
                     scrub: Callable[[str], str],
                     fake_id: Callable[[str], str],
                     id_map: dict[str, str],
                     slug_pair: tuple[str, str],
                     known_ids: set[str],
                     sanitize_name: Callable[[str], str],
                     sanitize_text: Callable[[str], str],
                     age_jitter: int = 0) -> dict[str, dict]:
    """De-identify every top-level sidecar JSON in `folder` into `out_dir`.

    `sanitize_name` renames files (may slugify); `sanitize_text` is the
    non-slugifying variant applied to every string value.
    Returns {source filename: {"output": path, "flags": [...]}}.
    """
    results: dict[str, dict] = {}
    for src in sorted(folder.glob("*.json")):
        deid = JsonDeidentifier(scrub=scrub, fake_id=fake_id,
                                id_map=id_map, slug_pair=slug_pair,
                                known_ids=known_ids, sanitize_text=sanitize_text,
                                age_jitter=age_jitter)
        data = json.loads(src.read_text())
        cleaned = deid.walk(data)
        if src.name.endswith(".metadata.json") and isinstance(cleaned, dict):
            deid.fix_metadata_offsets(cleaned)
            cleaned["pdf_filename"] = sanitize_name(cleaned.get("pdf_filename", ""))
            if cleaned.get("document_id"):
                cleaned["document_id"] = re.sub(
                    re.escape(slug_pair[0]), slug_pair[1],
                    cleaned["document_id"], flags=re.IGNORECASE)
        new_name = sanitize_name(src.name)
        dst = out_dir / new_name
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(json.dumps(cleaned, indent=2, ensure_ascii=False))
        results[src.name] = {"output": str(dst), "flags": deid.flags}
    return results


def audit_json_output(path: Path, real_values: list[str]) -> list[str]:
    """Return every real identifier string still present in the output JSON.
    Word-boundary matching, so a real token can't false-positive inside an
    unrelated longer word (e.g. "Scott" inside the surrogate "Prescott")."""
    text = path.read_text()
    hits = set()
    for v in real_values:
        if len(v) < 4:
            continue
        pat = re.escape(v)
        if v[:1].isalnum():
            pat = r"(?<![A-Za-z0-9])" + pat
        if v[-1:].isalnum():
            pat = pat + r"(?![A-Za-z0-9])"
        if re.search(pat, text, re.IGNORECASE):
            hits.add(v)
    return sorted(hits)
