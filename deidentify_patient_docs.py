#!/usr/bin/env python3
"""De-identify patient PDFs per the HIPAA Safe Harbor method (45 CFR 164.514(b)(2))
using SURROGATE REPLACEMENT ("hiding in plain sight").

Every one of the 18 Safe Harbor identifier categories is removed - but instead
of blanks or [PLACEHOLDER] tags, each value is replaced with a REALISTIC FAKE
that stays consistent across the patient's entire document bundle, so the data
remains fully coherent for model training while containing no real PHI:

  1  Names                  -> one fake persona (e.g. "WALKER, HAROLD"), used
                               everywhere, including initials badges
  2  Geo < state            -> fake street / fake city / fake ZIP (state kept)
  3  Dates / ages >= 90     -> every date shifted by one secret per-patient day
                               offset (timeline intervals preserved, MIMIC-style);
                               ages >= 90 aggregated to "90+"
  4/5 Phones & faxes        -> fictional NANP numbers (555-01xx), format kept
  6  Emails                 -> fake mailbox @example.com
  7  SSNs                   -> fabricated digits, format kept
  8-11, 18  MRN / policy / account / license / other unique IDs
                            -> random same-format values (digit->digit,
                               letter->letter), consistent per original value
  12/13 Vehicle/device IDs  -> random same-format values (contextual match)
  14 URLs                   -> example.com URL
  15 IPs                    -> TEST-NET address
  16/17 Biometrics/photos   -> not detectable in text; scanned pages are OCR'd,
                               PHI pixels blanked, and flagged for manual QA

Provider/clinician names, NPIs and PTANs are NOT patient identifiers under
Safe Harbor and are left intact by default (use --scrub-providers to replace
them with fake names/numbers as well).

Hidden channels are also cleaned: PDF /Info + XMP metadata wiped, all
hyperlinks deleted (URLs can carry PHI in query strings), AcroForm field
values rewritten, scanned pages OCR-redacted iteratively at several dpi.

The persona, date offset and value crosswalk live in deid_keys/<patient>.json.
That key file is the re-identification map: store it separately from the
output and never distribute the two together. Surrogates are random, never
derived from the real values (164.514(c)).

Usage:
    python deidentify_patient_docs.py [--input patient_docs] [--output patient_docs_deid]
"""

from __future__ import annotations

import argparse
import json
import random
import re
import secrets
import string
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

TOKEN_ALPHABET = string.ascii_uppercase + string.digits

MONTHS = (
    "January|February|March|April|May|June|July|August|September|October|November|December|"
    "Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"
)

FIRST_NAMES = {
    "M": ["Harold", "Raymond", "Eugene", "Vernon", "Clarence", "Leon", "Marvin",
          "Chester", "Willis", "Norman", "Earl", "Stanley", "Roland", "Gilbert"],
    "F": ["Dorothy", "Mildred", "Eleanor", "Bernice", "Lucille", "Vivian",
          "Geraldine", "Marion", "Thelma", "Beatrice", "Irene", "Estelle"],
}
LAST_NAMES = ["Walker", "Hayes", "Fleming", "Barrett", "Donovan", "Mercer",
              "Whitfield", "Calloway", "Prescott", "Langford", "Hollis",
              "Radcliffe", "Stanton", "Merriweather", "Kendall", "Ashford"]
STREET_WORDS = ["Maplewood", "Cedarbrook", "Willow Creek", "Stonegate", "Fairhaven",
                "Briarcliff", "Larkspur", "Juniper", "Coral Vine", "Sandpiper",
                "Palmetto Ridge", "Baywood", "Crestline", "Silver Oak"]
STREET_SUFFIX = ["Ln", "Dr", "Ave", "Ct", "Rd", "Way", "Blvd"]
FL_CITIES = [("ORLANDO", "32806"), ("JACKSONVILLE", "32210"), ("GAINESVILLE", "32601"),
             ("TALLAHASSEE", "32301"), ("OCALA", "34470"), ("MELBOURNE", "32901"),
             ("PENSACOLA", "32501"), ("DAYTONA BEACH", "32114")]
ORG_FIRST = ["Cypress Point", "Bayside", "Harborview", "Summit Ridge", "Palm Grove",
             "Lakecrest", "Silver Pine", "Magnolia", "Bluewater", "Oak Hollow"]
ORG_KIND = ["Wound Care", "Medical Group", "Health Services", "Care Partners",
            "Clinical Associates", "Health Alliance", "Medical Center"]


# ---------------------------------------------------------------------------
# surrogate store: original value -> fake value, persisted in the key file
# ---------------------------------------------------------------------------

class SurrogateStore:
    def __init__(self, saved: dict, seed: int):
        self.map: dict[str, str] = dict(saved)
        self.rng = random.Random(seed)

    def get(self, category: str, original: str, factory) -> str:
        key = f"{category}:{original}"
        if key not in self.map:
            self.map[key] = factory(self.rng, str(original))
        return self.map[key]


S: SurrogateStore = None      # set per patient in main()
PERSONA: dict = None          # idem
DATE_OFFSET = 0               # idem
AGE_JITTER = 0                # idem: +/- years applied to age AND to the DOB shift


def _same_format_id(rng: random.Random, original: str) -> str:
    """Random value with the exact character classes of the original."""
    for _ in range(20):
        out = []
        for i, c in enumerate(original):
            if c.isdigit():
                out.append(str(rng.randint(1, 9)) if i == 0 and c != "0"
                           else str(rng.randint(0, 9)))
            elif c.isalpha() and c.isupper():
                out.append(rng.choice(string.ascii_uppercase))
            elif c.isalpha():
                out.append(rng.choice(string.ascii_lowercase))
            else:
                out.append(c)
        fake = "".join(out)
        if fake != original:
            return fake
    return "".join(out)


def _digits_into_template(template: str, digits: str) -> str:
    """Pour `digits` into `template`, replacing its digit positions in order."""
    it = iter(digits)
    return "".join(next(it, "0") if c.isdigit() else c for c in template)


def fake_id(original: str) -> str:
    return S.get("id", original, _same_format_id)


def fake_phone(original: str) -> str:
    def factory(rng, orig):
        n = sum(c.isdigit() for c in orig)
        area = rng.choice(["321", "352", "386", "407", "561", "727", "772", "863", "904"])
        line = f"01{rng.randint(0, 99):02d}"
        if n == 11:
            digits = "1" + area + "555" + line
        elif n == 10:
            digits = area + "555" + line
        elif n == 7:
            digits = "555" + line
        else:
            digits = "".join(str(rng.randint(0, 9)) for _ in range(n))
        return _digits_into_template(orig, digits)
    return S.get("phone", original, factory)


def fake_ssn(original: str) -> str:
    def factory(rng, orig):
        digits = "9" + "".join(str(rng.randint(0, 9)) for _ in range(8))
        return _digits_into_template(orig, digits)
    return S.get("ssn", original, factory)


def fake_email(original: str) -> str:
    def factory(rng, orig):
        return f"contact{rng.randint(100, 999)}@example.com"
    return S.get("email", original, factory)


def fake_street(original: str) -> str:
    def factory(rng, orig):
        return f"{rng.randint(100, 9899)} {rng.choice(STREET_WORDS)} {rng.choice(STREET_SUFFIX)}"
    return S.get("street", original, factory)


def fake_person(original: str) -> str:
    """A consistent fake full name for a non-patient person (relative, staff)."""
    def factory(rng, orig):
        return f"{rng.choice(FIRST_NAMES['M'] + FIRST_NAMES['F'])} {rng.choice(LAST_NAMES)}"
    fake = S.get("person", original.lower(), factory)
    return fake.upper() if original.isupper() else fake


def fake_org(original: str) -> str:
    """A consistent fake organization/facility name."""
    def factory(rng, orig):
        return f"{rng.choice(ORG_FIRST)} {rng.choice(ORG_KIND)}"
    fake = S.get("org", original.lower(), factory)
    return fake.upper() if original.isupper() else fake


def fake_city(original: str) -> str:
    def factory(rng, orig):
        return rng.choice(FL_CITIES)[0]
    fake = S.get("city", original.lower(), factory)
    return fake if original.isupper() else fake.title()


def fake_zip(original: str) -> str:
    def factory(rng, orig):
        return rng.choice(FL_CITIES)[1]
    return S.get("zip", original, factory)


_OCR_CONFUSABLES = str.maketrans({"l": "1", "I": "1", "o": "0", "O": "0"})
_DATE_FORMATS = ["%m/%d/%Y", "%m-%d-%Y", "%Y-%m-%d", "%m/%d/%y",
                 "%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y"]


def _parse_date(s: str):
    s = re.sub(r"\s+", " ", s.strip())
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt), fmt
        except ValueError:
            continue
    return None, None


def _shift_date(original: str, days: int) -> str:
    """Shift a date string by `days`, keeping the original format."""
    m = re.match(r"^(\d{4}-\d{2}-\d{2})([T ].*)$", original)
    if m:  # ISO datetime: shift the date part, keep the time part
        return _shift_date(m.group(1), days) + m.group(2)
    normalized = original.translate(_OCR_CONFUSABLES)
    dt, fmt = _parse_date(normalized)
    if dt is None:
        m = re.search(r"(19|20)\d{2}", normalized)
        return m.group(0) if m else original  # last resort: year only
    if dt.year >= 9000 or dt.year <= 1900:  # sentinel dates, not patient dates
        return original
    try:
        shifted = dt + timedelta(days=days)
    except OverflowError:
        return original
    out = shifted.strftime(fmt)
    if fmt in ("%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y"):  # unpad like source docs
        out = re.sub(r"\b0(\d)", r"\1", out)
    return out


def fake_date(original: str) -> str:
    """Shift a date by the per-patient offset, keeping the original format."""
    return _shift_date(original, DATE_OFFSET)


def fake_dob(original: str) -> str:
    """The DOB additionally moves by the age jitter, so the displayed age
    (visit year minus birth year) changes consistently everywhere."""
    return _shift_date(original, DATE_OFFSET - AGE_JITTER * 365)


def fake_age(raw: str) -> str:
    n = int(raw) + AGE_JITTER
    if int(raw) >= 90 or n >= 90:
        return "90+"
    return str(max(n, 1))


def fake_monthday(original: str) -> str:
    """'Jul 14' (no year): shift assuming the bundle's nominal year."""
    dt, _ = _parse_date(f"{original} {PERSONA.get('nominal_year', 2026)}")
    if dt is None:
        return "[DATE]"
    shifted = dt + timedelta(days=DATE_OFFSET)
    return f"{shifted:%b} {shifted.day}"


def render_name(value: str, persona: dict, name_parts: list[str]) -> str:
    """Persona name rendered in the same shape/case as the original mention."""
    first, last = persona["first"], persona["last"]
    if "," in value:
        out = f"{last}, {first}"
    elif " " in value:
        real_last_first = (len(name_parts) == 2
                           and value.lower().startswith(name_parts[1].lower()))
        out = f"{last} {first}" if real_last_first else f"{first} {last}"
    elif len(name_parts) == 2 and value.lower() == name_parts[0].lower():
        out = first
    else:
        out = last
    return out.upper() if value.isupper() else out


# ---------------------------------------------------------------------------
# patterns swept on every page, beyond known values from the sidecar JSONs
# ---------------------------------------------------------------------------

GENERIC_PATTERNS = [
    # 3. dates -> shifted by the per-patient offset.
    # NB: \b does NOT exist between a digit and a letter (both are \w), so
    # run-together OCR text like "03/18/2026ED" needs lookarounds, not \b.
    (re.compile(r"(?<![\d/])\d{1,2}/\d{1,2}/\d{4}(?!\d)"), 0, lambda m: fake_date(m.group(0))),
    (re.compile(r"(?<![\d-])\d{1,2}-\d{1,2}-\d{4}(?!\d)"), 0, lambda m: fake_date(m.group(0))),
    (re.compile(r"(?<![\d-])\d{4}-\d{2}-\d{2}(?!\d)"), 0, lambda m: fake_date(m.group(0))),
    (re.compile(rf"\b(?:{MONTHS})\.?\s+\d{{1,2}},?\s+\d{{4}}(?!\d)"), 0,
     lambda m: fake_date(m.group(0))),
    (re.compile(r"(?<![\d/])\d{1,2}/\d{1,2}/\d{2}(?![\d/])"), 0, lambda m: fake_date(m.group(0))),
    (re.compile(rf"\b(?:{MONTHS})\.?\s+\d{{1,2}}(?!\d)(?!\s*,?\s*\d{{4}})"), 0,
     lambda m: fake_monthday(m.group(0))),
    # OCR text: dates with digit/letter confusables (04/0l/2026). Fires ONLY
    # when a confusable letter is present - pure-digit dates belong to the
    # pattern above, and matching both would shift the date twice.
    (re.compile(r"(?<![\d/])[\dlIoO]{1,2}/[\dlIoO]{1,2}/[12][\dlIoO]{3}(?!\d)"), 0,
     lambda m: fake_date(m.group(0)) if re.search(r"[lIoO]", m.group(0)) else None),
    # 3. ages: jittered by the per-patient offset (consistent with the shifted
    # DOB); 90+ aggregated. Whole contextual match is replaced - the bare
    # number alone ("85") is far too generic a literal to substitute globally.
    (re.compile(r"(?i)\b(\d{2,3})(\s*(?:yrs?|years?[ -]old|y/?o))\b"), 0,
     lambda m: fake_age(m.group(1)) + m.group(2)),
    (re.compile(r"(?i)\b(AGE:?\s*)(\d{2,3})\b"), 0,
     lambda m: m.group(1) + fake_age(m.group(2))),
    # 4/5. phones & faxes (incl. run-together fax-header numbers)
    (re.compile(r"\(\d{3}\)\s*\d{3}[-.\s]?\d{4}"), 0, lambda m: fake_phone(m.group(0))),
    (re.compile(r"\b\d{3}[-.]\d{3}[-.]\d{4}\b"), 0, lambda m: fake_phone(m.group(0))),
    (re.compile(r"(?i)\b(?:fax|tel|phone|from)\b\D{0,30}?(1?[2-9]\d{9})\b"), 1,
     lambda m: fake_phone(m.group(1))),
    # bare 10-digit NANP numbers in prose ("...the patient's PCP 8134174767...");
    # area code and exchange must both start [2-9], which excludes NPIs/MRNs
    # beginning with 0/1 and most record IDs
    (re.compile(r"(?<!\d)1?([2-9]\d{2}[2-9]\d{2}\d{4})(?!\d)"), 1,
     lambda m: fake_phone(m.group(1))),
    # 6. emails
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"), 0, lambda m: fake_email(m.group(0))),
    # 7. SSNs
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), 0, lambda m: fake_ssn(m.group(0))),
    # 14. URLs
    (re.compile(r"\bhttps?://\S+|\bwww\.\S+"), 0, lambda m: "https://www.example.com"),
    # 15. IP addresses
    (re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"), 0,
     lambda m: "203.0.113." + m.group(0).rsplit(".", 1)[1]),
    # 8/9/10/11/12/13/18. contextual identifier fields.
    # Same-line only ([ \t], never \s -> would cross newlines) and the captured
    # ID must contain a digit, so field labels are never mistaken for values.
    (re.compile(r"(?i)\bPolicy[ \t]*#?[ \t]*:[ \t]*([A-Z0-9]*\d[A-Z0-9]{4,})"), 1,
     lambda m: fake_id(m.group(1))),
    (re.compile(r"(?i)\b(?:Member|Beneficiary|Subscriber)[ \t]*(?:ID|#)[ \t]*:?[ \t]*"
                r"([A-Z0-9]*\d[A-Z0-9]{4,})"), 1, lambda m: fake_id(m.group(1))),
    (re.compile(r"(?i)\bMRN:?[ \t]*([A-Z0-9]*\d[A-Z0-9]{2,})"), 1, lambda m: fake_id(m.group(1))),
    (re.compile(r"(?i)\bAcct[ \t]*#?[ \t]*:?[ \t]*(\d{3,})"), 1, lambda m: fake_id(m.group(1))),
    (re.compile(r"(?i)\bAccount[ \t]*(?:number|#)[ \t]*:?[ \t]*(\d{3,})"), 1,
     lambda m: fake_id(m.group(1))),
    (re.compile(r"(?i)\bPATIENT[ \t]+ID/?#?:?[ \t]*(\d{3,})"), 1, lambda m: fake_id(m.group(1))),
    (re.compile(r"(?i)\b(?:license|certificate)[ \t]*(?:number|no\.?|#)[ \t]*:?[ \t]*"
                r"([A-Z0-9-]*\d[A-Z0-9-]{2,})"), 1, lambda m: fake_id(m.group(1))),
    (re.compile(r"(?i)\b(?:VIN|license plate)[ \t]*:?[ \t]*([A-Z0-9-]*\d[A-Z0-9-]{2,})"), 1,
     lambda m: fake_id(m.group(1))),
    (re.compile(r"(?i)\bserial[ \t]*(?:number|no\.?|#)[ \t]*:?[ \t]*([A-Z0-9-]*\d[A-Z0-9-]{2,})"),
     1, lambda m: fake_id(m.group(1))),
    # record-level unique numbers (#18): order/transaction/customer/auth/chart
    # IDs. \s may cross a newline here; the capture is digits-only, so a field
    # label can never be swallowed the way "BIRTH DATE" once was.
    (re.compile(r"(?i)\b(?:Order|Transaction|Customer|Authorization|Auth|Claim|Chart|Encounter)"
                r"\s*(?:ID|#|No\.?|Number)?\s*:?\s*(\d{5,})"), 1, lambda m: fake_id(m.group(1))),
    (re.compile(r"(?i)\bTIN(?:\s*or\s*SSN)?\s*:?\s*(\d{6,})"), 1, lambda m: fake_id(m.group(1))),
    # patient's preferred pharmacy: store number + street line reveal locality
    (re.compile(r"(?i)\bPharmacy\s*#\s*(\d{3,})"), 1, lambda m: fake_id(m.group(1))),
    (re.compile(r"(?i)Preferred\s+Pharmacy:\s*\n[^\n]*\n(\d{1,5}[^\n]{3,60})"), 1,
     lambda m: fake_street(m.group(1))),
]

# Only with --scrub-providers: clinician identifiers (not required by Safe
# Harbor - they identify the provider, not the patient).
PROVIDER_ID_PATTERNS = [
    (re.compile(r"(?i)\bNPI:?\s*(\d{10})\b"), 1, lambda m: fake_id(m.group(1))),
    (re.compile(r"(?i)\bPTAN:?\s*([A-Z]{0,3}\d{4,}[A-Z0-9]*)\b"), 1,
     lambda m: fake_id(m.group(1))),
    (re.compile(r"\b[12]\d{9}\b"), 0, lambda m: fake_id(m.group(0))),
]

# Clinician-name discovery (used only with --scrub-providers).
CREDS = r"(?:MD|DO|NP|PA|RN|LPN|ARNP|APRN|DNP|FNP|AGNP|PA-C|CNA|CNS)"
CRED_SET = {c for c in "MD DO NP PA RN LPN ARNP APRN DNP FNP AGNP PA-C CNA CNS".split()}
CRED_SET |= {"NPI", "PTAN", "DEA", "LICENSE"}  # field labels trailing a name
PROVIDER_NAME_RX = [
    re.compile(rf"\b([A-Z][\w'\-]+(?:\s+[A-Z][\w'\-]+)?\s*,\s*[A-Z][\w'\-]+)\s*,?\s+"
               rf"{CREDS}(?:[ ,]+{CREDS})*\b"),
    re.compile(rf"\b([A-Z][\w'\-]+\s+[A-Z][\w'\-]+)\s+{CREDS}\b"),
    re.compile(r"(?i)\b(?:referring\s+)?(?:provider|physician|medical\s+director|"
               r"signed\s+by|rendering\s+provider|case\s+manager|caller|"
               r"prepared\s+by|completed\s+by|entered\s+by)\s*:?\s+"
               r"([A-Z][\w'\-]+(?:[ ,]+[A-Z][\w'\-]+){1,3})"),
]


def normalize_person(raw: str) -> tuple[str, list[str]]:
    """Strip credentials, return (normalized key, name variants)."""
    tokens = [t for t in re.split(r"[,\s]+", raw.strip()) if t]
    while tokens and tokens[-1].upper().strip(".") in CRED_SET:
        tokens.pop()
    if len(tokens) < 2 or not all(re.fullmatch(r"[\w'\-\.]+", t) for t in tokens):
        return "", []
    key = " ".join(sorted(t.lower() for t in tokens))
    variants = {" ".join(tokens)}
    if "," in raw:
        last, first = [p.strip() for p in raw.split(",", 1)]
        first = " ".join(t for t in first.split() if t.upper() not in CRED_SET)
        if first and last:
            variants |= {f"{last}, {first}", f"{last},{first}", f"{first} {last}"}
    else:
        variants |= {f"{tokens[-1]}, {' '.join(tokens[:-1])}",
                     f"{tokens[-1]},{' '.join(tokens[:-1])}"}
    return key, sorted(variants)


def discover_providers(folder: Path) -> dict[str, str]:
    """Scan every PDF (text + form fields) for clinician names; map each
    variant to a consistent fake person (only used with --scrub-providers)."""
    found: dict[str, set[str]] = {}
    for pdf in sorted(folder.rglob("*.pdf")):
        doc = pymupdf.open(pdf)
        for page in doc:
            text = page.get_text()
            for w in page.widgets() or []:
                if isinstance(w.field_value, str):
                    text += "\n" + w.field_value
            for rx in PROVIDER_NAME_RX:
                for m in rx.finditer(text):
                    key, variants = normalize_person(m.group(1))
                    if key:
                        found.setdefault(key, set()).update(variants)
        doc.close()

    def person_factory(rng, _orig):
        return f"{rng.choice(FIRST_NAMES['M'] + FIRST_NAMES['F'])} {rng.choice(LAST_NAMES)}"

    out: dict[str, str] = {}
    for key in sorted(found):
        fake = S.get("provider", key, person_factory)
        ffirst, flast = fake.split(" ", 1)
        for v in found[key]:
            if "," in v:
                fake_v = f"{flast}, {ffirst}"
            else:
                fake_v = f"{ffirst} {flast}"
            out[v] = fake_v.upper() if v.isupper() else fake_v
    return out


def new_token() -> str:
    return "PATIENT-" + "".join(secrets.choice(TOKEN_ALPHABET) for _ in range(6))


def date_variants(iso: str) -> list[str]:
    """All common renderings of a date, for exact-match replacement."""
    try:
        d = datetime.fromisoformat(iso.split("T")[0])
    except ValueError:
        return [iso]
    return list({
        d.strftime("%m/%d/%Y"), f"{d.month}/{d.day}/{d.year}",
        f"{d.month}/{d.day:02d}/{d.year}", f"{d.month:02d}/{d.day}/{d.year}",
        d.strftime("%m-%d-%Y"), f"{d.month}-{d.day}-{d.year}",
        d.strftime("%Y-%m-%d"), d.strftime("%B %d, %Y"), d.strftime("%b %d, %Y"),
        f"{d.strftime('%B')} {d.day}, {d.year}",
    })


def name_variants(first: str, last: str) -> list[str]:
    full = f"{first} {last}"
    return [
        f"{last}, {first}", f"{last},{first}", full, f"{last} {first}",
        f"{last},  {first}", f"{first}  {last}",
        first, last,  # bare given/family names, matched case-insensitively
    ]


def _dig(obj, *keys):
    for k in keys:
        obj = obj.get(k) if isinstance(obj, dict) else None
        if obj is None:
            return None
    return obj


# JSON keys whose values are identifying numbers (Safe Harbor 7-11, 13, 18)
ID_KEY_RX = re.compile(
    r"(?i)policy.?number|subscriber.?id|member.?(?:id|number)|beneficiar|"
    r"group.?number|\bmrn\b|medicalrecord|account.?number|\bssn\b|serial.?number"
)


def walk_for_ids(obj, add):
    """Recursively pull identifier values out of a sidecar JSON payload."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (str, int)) and ID_KEY_RX.search(k) and len(str(v)) >= 5:
                add(v, "[ID]")
            else:
                walk_for_ids(v, add)
    elif isinstance(obj, list):
        for v in obj:
            walk_for_ids(v, add)


def harvest_record_ids(folder: Path) -> dict[str, str]:
    """Collect the patient's encounter and document-scan IDs (#18); each maps
    to a random same-format number so cross-references stay coherent."""
    enc_ids: set[str] = set()
    doc_ids: set[str] = set()
    for drk in folder.glob("*.drk.json"):
        data = json.loads(drk.read_text())
        for note in data.get("downloaded_encounter_notes") or data.get("encounter_notes") or []:
            if isinstance(note, dict) and note.get("encounter_id"):
                enc_ids.add(str(note["encounter_id"]))
        for d in data.get("downloaded_documents") or []:
            if isinstance(d, dict) and d.get("scan_id"):
                doc_ids.add(str(d["scan_id"]))
    for pdf in folder.rglob("*.pdf"):  # fallback: IDs embedded in filenames
        m = re.match(r"(?i)encounter[-_](\d{4,})", pdf.name)
        if m:
            enc_ids.add(m.group(1))
        m = re.match(r"(\d{4,})[-_]", pdf.name)
        if m:
            doc_ids.add(m.group(1))
    return {v: "[ID]" for v in enc_ids | doc_ids}


def harvest_phi(folder: Path, scrub_staff: bool, scrub_facilities: bool = True):
    """Collect the patient's known identifier values from the sidecar JSONs.

    Returns (value -> category-placeholder map, display name, name parts,
    dynamic name regexes, record-id map, gender). Placeholders are resolved
    into surrogate values by finalize_known().
    """
    repl: dict[str, str] = {}
    first = last = ""
    gender = "M"
    staff_names: set[str] = set()

    def add(value, replacement):
        if value and str(value).strip():
            repl[str(value).strip()] = replacement

    def collect_staff(obj):
        """Employee names/usernames under user-attribution JSON keys."""
        if isinstance(obj, dict):
            for k, v in obj.items():
                if (isinstance(v, str) and v.strip() and re.search(
                        r"(?i)(?:createdby|assigned|manager|signer)\w*name|^user_?name$", k)):
                    val = v.strip()
                    if re.fullmatch(r"[A-Za-z'\-]{2,}(?: [A-Za-z'\-]{2,}){1,2}", val):
                        staff_names.add(val)
                    elif re.fullmatch(r"[A-Za-z][\w.\-]{3,}", val):
                        add(val, "{USERNAME}")  # system username, e.g. "cogabang"
                else:
                    collect_staff(v)
        elif isinstance(obj, list):
            for v in obj:
                collect_staff(v)

    def collect_orgs(obj):
        """Facility/agency/company names anywhere in the payload."""
        if isinstance(obj, dict):
            for k, v in obj.items():
                if (isinstance(v, str) and 3 <= len(v.strip()) <= 60
                        and re.search(r"(?i)facility|agency|company|organization|practice", k)
                        and re.search(r"[A-Za-z]{3}", v)):
                    add(v.strip(), "{ORG}")
                else:
                    collect_orgs(v)
        elif isinstance(obj, list):
            for v in obj:
                collect_orgs(v)

    for meta in folder.glob("*.metadata.json"):
        data = json.loads(meta.read_text())
        for ent in data.get("entities", []):
            v, t = ent.get("value"), ent.get("type", "")
            if t == "PATIENT_NAME":
                add(v, "{NAME}")
                if "," in (v or ""):
                    last, first = [p.strip() for p in v.split(",", 1)]
            elif t == "DATE_OF_BIRTH":
                dt, _fmt = _parse_date(v)
                for dv in (date_variants(dt.date().isoformat()) if dt else [v]):
                    add(dv, "{DATE}")
            elif t == "PATIENT_PHONE_NUMBER":
                add(v, "{PHONE}")
            elif t == "PATIENT_ADDRESS":
                add(v, "{FULLADDR}")
                # cover street/city mentioned on their own, not only the
                # full "street, city, ST zip" string
                parts = [p.strip() for p in v.split(",")]
                if parts and re.match(r"\d", parts[0]):
                    add(parts[0], "{STREET}")
                if len(parts) >= 3:
                    add(parts[-2], "{CITY}")
            elif "EMAIL" in t:
                add(v, "{EMAIL}")
            else:
                add(v, "[ID]")

    for drk in folder.glob("*.drk.json"):
        data = json.loads(drk.read_text())
        collect_staff(data)  # staff are always scrubbed; only clinicians opt out
        if scrub_facilities:
            collect_orgs(data)
        for block in data.get("patient_information", []):
            demo = _dig(block, "data", "data") or {}
            if not isinstance(demo, dict):
                continue
            first = demo.get("firstName") or first
            last = demo.get("lastName") or last
            g = str(demo.get("gender") or "")
            if g:
                gender = "F" if g.lower().startswith("f") else "M"
            add(demo.get("fullName"), "{NAME}")
            add(demo.get("email"), "{EMAIL}")
            add(demo.get("mrn"), "[ID]")
            if scrub_facilities:
                add(demo.get("facilityName"), "{ORG}")
                add(demo.get("homeHealthCompanyName"), "{ORG}")
            add(demo.get("address1"), "{STREET}")
            add(demo.get("address2"), "{STREET}")
            add(demo.get("fullAddress"), "{FULLADDR}")
            add(demo.get("city"), "{CITY}")
            for key in ("phone", "phoneNumber", "homePhone", "cellPhone", "mobilePhone"):
                add(demo.get(key), "{PHONE}")
            zc = str(demo.get("zip") or demo.get("zipCode") or "")
            if re.fullmatch(r"\d{5}(-\d{4})?", zc):
                add(zc, "{ZIP}")
            dob = demo.get("dateOfBirth")
            if dob:
                add(dob, "{DATE}")  # full ISO datetime as stored in the EMR
                for dv in date_variants(dob):
                    add(dv, "{DATE}")
        add(data.get("patient_id"), "[ID]")
        walk_for_ids(data.get("insurance"), add)
        walk_for_ids(data.get("billing"), add)
        if scrub_facilities:
            # EMR page titles carry the practice's compact name ("- WestCoastWound")
            for note in (data.get("encounter_notes") or []) + \
                        (data.get("downloaded_encounter_notes") or []):
                title = _dig(note, "page", "title") if isinstance(note, dict) else None
                if isinstance(title, str) and title.strip(" -|"):
                    add(title.strip(" -|"), "{ORG}")

    for mon in folder.glob("*.monday.json"):
        data = json.loads(mon.read_text())
        nm = data.get("name", "")
        if "," in nm:
            l, f = [p.strip() for p in nm.split(",", 1)]
            first, last = first or f, last or l
        add(nm, "{NAME}")
        for col in data.get("columns", []):
            title, text = (col.get("title") or "").lower(), col.get("text")
            if not text:
                continue
            if "dob" in title or "birth" in title:
                for dv in date_variants(text):
                    add(dv, "{DATE}")
            elif "email" in title and "@" in text:
                add(text, "{EMAIL}")
            elif "phone" in title:
                add(text, "{PHONE}")
            elif col.get("type") == "people":
                staff_names.add(text.strip())
            elif scrub_facilities and ("agency" in title or "referring" in title):
                add(text.strip(), "{ORG}")

    for act in folder.glob("*.activity.json"):
        data = json.loads(act.read_text())
        collect_staff(data)
        if scrub_facilities:
            for entry in data.get("activities", []):
                col = str(entry.get("column") or "")
                val = entry.get("value")
                if isinstance(val, str) and val.strip() and re.search(
                        r"(?i)agency|referring", col):
                    add(val.strip(), "{ORG}")
        nm = data.get("name", "")
        if "," in nm:
            l, f = [p.strip() for p in nm.split(",", 1)]
            first, last = first or f, last or l
        add(nm, "{NAME}")
        dob = data.get("date_of_birth")
        if dob:
            for dv in date_variants(dob):
                add(dv, "{DATE}")

    name_rx: list[re.Pattern] = []
    if first and last:
        for v in name_variants(first, last):
            repl.setdefault(v, "{NAME}")
        # catch middle initials / suffixes: "Butler, Alva J", "Alva J. Butler"
        f, l = re.escape(first), re.escape(last)
        name_rx = [
            re.compile(rf"\b{l}\s*,\s*{f}(?:\s+[A-Z]\.?)?\b", re.IGNORECASE),
            re.compile(rf"\b{f}\s+(?:[A-Z]\.?\s+)?{l}\b", re.IGNORECASE),
        ]

    # ZIPs inside any harvested address string
    for v in list(repl):
        for zc in re.findall(r"\b(\d{5})(?:-\d{4})?\b", v):
            repl.setdefault(zc, "{ZIP}")

    id_map = harvest_record_ids(folder)
    for v in id_map:
        repl.setdefault(v, "[ID]")

    for nm in sorted(staff_names):
        repl.setdefault(nm, "{STAFF}")

    display = f"{first} {last}".strip() or folder.name
    return repl, display, [p for p in (first, last) if p], name_rx, id_map, gender


def finalize_known(known: dict[str, str], persona: dict,
                   name_parts: list[str]) -> dict[str, str]:
    """Resolve category placeholders into concrete surrogate values."""
    out: dict[str, str] = {}
    for value, ph in known.items():
        if ph == "{NAME}":
            out[value] = render_name(value, persona, name_parts)
        elif ph == "{DATE}":
            out[value] = fake_dob(value)
        elif ph == "{PHONE}":
            if re.search(r"[A-Za-z]{2,}", value):
                # harvested "phone" fields sometimes hold prose around the
                # number ("N 813-... ext. 102 Amedisys TAN HH spoke"); the
                # format-preserving fake would keep every word, and mapping
                # the full string would shadow the org/name replacements
                # inside it. Fake only the number-shaped substrings.
                for m in re.finditer(r"(?<!\d)\d[\d\s().\-]{7,17}\d(?!\d)", value):
                    out.setdefault(m.group(0), fake_phone(m.group(0)))
            else:
                out[value] = fake_phone(value)
        elif ph == "{EMAIL}":
            out[value] = persona["email"]
        elif ph == "{STREET}":
            out[value] = (persona["street"].upper() if value.isupper()
                          else persona["street"])
        elif ph == "{CITY}":
            out[value] = (persona["city"] if value.isupper()
                          else persona["city"].title())
        elif ph == "{ZIP}":
            out[value] = persona["zip"]
        elif ph == "{FULLADDR}":
            addr = f"{persona['street']}, {persona['city']} FL {persona['zip']}"
            out[value] = addr.upper() if value.isupper() else addr
        elif ph == "{STAFF}":
            fake = fake_person(value)
            out[value] = fake
            # bare first/last mentions in prose ("Hi Jucelle!", "TEAMS CM JUCELLE")
            real_toks = [t for t in re.split(r"[,\s]+", value) if len(t) >= 4]
            fake_toks = fake.split()
            for i, tok in enumerate(real_toks):
                out.setdefault(tok, fake_toks[min(i, len(fake_toks) - 1)])
        elif ph == "{ORG}":
            fake = fake_org(value)
            # strip trailing phone/parenthetical noise, then cover the stem
            cleaned = re.sub(r"[(\d].*$", "", value).strip(" -|,")
            out[value] = fake
            if cleaned and cleaned.lower() != value.lower():
                out.setdefault(cleaned, fake)
            toks = cleaned.split()
            if len(toks) >= 3:  # "Olive Health Florida" -> "Olive Health"
                out.setdefault(" ".join(toks[:2]), fake)
        elif ph == "{USERNAME}":
            out[value] = fake_id(value)
        elif re.fullmatch(r"[A-Za-z'\-]{2,}(?: [A-Za-z'\-]{2,}){1,2}", value):
            # a person-shaped value tagged as a generic ID (e.g. an emergency
            # contact): a fake NAME, not a letter-scramble ("Mlypx Upjgln")
            out[value] = fake_person(value)
        else:  # [ID] and any other unique number/code
            out[value] = fake_id(value)
    return out


def collect_page_jobs(text: str, known: dict[str, str],
                      name_rx: list[re.Pattern]) -> dict[str, str]:
    """Decide which literal strings on this page get which replacement.

    Matches are gathered as text spans and overlaps resolved BEFORE returning:
    two patterns matching overlapping text (e.g. a phone caught by two rules
    with different spans) would otherwise both locate rects and draw twice.
    """
    spans: list[tuple[int, int, str, str]] = []  # start, end, literal, replacement
    for rx in name_rx:
        for m in rx.finditer(text):
            spans.append((m.start(), m.end(), m.group(0), "{ALIAS}"))
    for value, replacement in known.items():
        if " " in value:
            # tolerate variable whitespace between words ("Arnaldo  Gomez")
            pat = r"[\s,]+".join(re.escape(t) for t in re.split(r"[\s,]+", value) if t)
        else:
            pat = re.escape(value)
        if value[:1].isalnum():
            pat = r"(?<![A-Za-z0-9])" + pat
        if value[-1:].isalnum():
            pat = pat + r"(?![A-Za-z0-9])"
        for m in re.finditer(pat, text, re.IGNORECASE):
            spans.append((m.start(), m.end(), m.group(0), replacement))
    for rx, group, fn in GENERIC_PATTERNS:
        for m in rx.finditer(text):
            replacement = fn(m)
            if replacement is None:
                continue
            spans.append((m.start(group), m.end(group), m.group(group), replacement))
    # earliest start wins; ties prefer longer spans, then earlier source
    # (name regex > known value > generic pattern, by insertion order)
    spans.sort(key=lambda t: (t[0], -(t[1] - t[0])))
    jobs: dict[str, str] = {}
    pos = 0
    for start, end, literal, replacement in spans:
        if start < pos:
            continue  # overlaps a span already claimed
        if replacement != literal:  # no-op replacements (sentinel dates) skipped
            jobs.setdefault(literal, replacement)
        pos = end
    return jobs


def scrub_string(s: str, known: dict[str, str], name_rx: list[re.Pattern],
                 alias: str) -> str:
    """Apply all replacements to a plain string (form field values, JSON values).

    All matches are located against the ORIGINAL string and applied in one
    rebuild. Sequential re.sub passes would let a later pattern re-match an
    already-inserted surrogate (a fake date is still date-shaped), shifting
    dates twice and re-faking IDs inconsistently.
    """
    matches: list[tuple[int, int, str]] = []
    for rx in name_rx:
        for m in rx.finditer(s):
            matches.append((m.start(), m.end(), alias))
    for value, replacement in sorted(known.items(), key=lambda kv: -len(kv[0])):
        if " " in value:
            pat = r"[\s,]+".join(re.escape(t) for t in re.split(r"[\s,]+", value) if t)
        else:
            pat = re.escape(value)
        # explicit alnum lookarounds, not \b: underscores and digit/letter
        # junctions ("_Butler_", "2026Date") are \w so \b fails there
        if value[:1].isalnum():
            pat = r"(?<![A-Za-z0-9])" + pat
        if value[-1:].isalnum():
            pat = pat + r"(?![A-Za-z0-9])"
        for m in re.finditer(pat, s, re.IGNORECASE):
            matches.append((m.start(), m.end(), replacement))
    for rx, group, fn in GENERIC_PATTERNS:
        for m in rx.finditer(s):
            r = fn(m)
            if r is not None:
                matches.append((m.start(group), m.end(group), r))
    # earliest start wins; at equal start prefer the longer span, then the
    # earlier source (name regex > known value > generic pattern)
    matches.sort(key=lambda t: (t[0], -(t[1] - t[0])))
    out: list[str] = []
    pos = 0
    for start, end, replacement in matches:
        if start < pos:
            continue  # overlaps a replacement already applied
        out.append(s[pos:start])
        out.append(replacement)
        pos = end
    out.append(s[pos:])
    return "".join(out)


def overlaps(a: pymupdf.Rect, b: pymupdf.Rect) -> bool:
    """True when two rects cover substantially the same area. Adjacent lines
    can touch by a fraction of a point; that must not count as a duplicate."""
    ix = min(a.x1, b.x1) - max(a.x0, b.x0)
    iy = min(a.y1, b.y1) - max(a.y0, b.y0)
    if ix <= 0 or iy <= 0:
        return False
    smaller = min(abs(a) or 1.0, abs(b) or 1.0)  # abs(Rect) is its area
    return (ix * iy) / smaller > 0.4


def locate_literal(page, textpage, literal: str, page_words) -> list[list[pymupdf.Rect]]:
    """All occurrences of `literal` as groups of rects.

    Multi-word literals use word-box sequence matching FIRST: it keeps one
    occurrence as one group even across line breaks (search_for returns one
    rect per line, which would draw the replacement once per line) and it
    tolerates irregular inter-word spacing. search_for supplements for
    occurrences word matching can't segment; single tokens use search_for."""
    toks = [t.lower() for t in re.split(r"[\s,]+", literal) if t]
    groups: list[list[pymupdf.Rect]] = []
    wl = [w[4].strip(",.;:()").lower() for w in page_words]
    if len(toks) > 1:
        for i in range(len(wl) - len(toks) + 1):
            if all(wl[i + j] == toks[j] for j in range(len(toks))):
                groups.append([pymupdf.Rect(page_words[i + j][:4])
                               for j in range(len(toks))])
    elif len(literal) < 6:
        # short single tokens must match whole words only: search_for is a
        # substring search, and e.g. "AB" would hit inside "Lab"/"about"
        for i, w in enumerate(page_words):
            if wl[i] == literal.lower():
                groups.append([pymupdf.Rect(w[:4])])
        return groups
    for r in page.search_for(literal, textpage=textpage):
        if not any(overlaps(r, o) for grp in groups for o in grp):
            groups.append([r])
    return groups


def match_font(page, rect: pymupdf.Rect, text: str) -> tuple[str, float]:
    """Font name + size matching the text originally inside `rect`, so the
    replacement blends in. Size shrinks until `text` fits the rect width."""
    fontname, size = "helv", 0.0
    try:
        d = page.get_text("dict", clip=rect)
        spans = [s for b in d.get("blocks", []) for l in b.get("lines", [])
                 for s in l.get("spans", [])]
        if spans:
            s0 = max(spans, key=lambda s: len(s.get("text", "")))
            size = float(s0.get("size") or 0)
            fname = (s0.get("font") or "").lower()
            bold = any(w in fname for w in ("bold", "black", "heavy"))
            italic = "italic" in fname or "oblique" in fname
            if "courier" in fname or "mono" in fname:
                fontname = "cobo" if bold else ("coit" if italic else "cour")
            elif any(w in fname for w in ("times", "roman", "georgia", "garamond",
                                          "book", "serif")) and "sans" not in fname:
                fontname = "tibo" if bold else ("tiit" if italic else "tiro")
            else:
                fontname = "hebo" if bold else ("heit" if italic else "helv")
    except Exception:
        pass
    if size <= 0:
        size = max(5.0, min(rect.height * 0.78, 14.0))
    # slight overflow is fine (looks natural); shrink only when clearly too wide
    if rect.width > 4:
        while size > 4 and pymupdf.get_text_length(
                text, fontname=fontname, fontsize=size) > rect.width * 1.12:
            size *= 0.94
    return fontname, size


def _expand_adjacent(group: list[pymupdf.Rect], page_words,
                     already: list[pymupdf.Rect]) -> list[pymupdf.Rect]:
    """Grow a scan wipe group with immediately adjacent same-line word boxes
    (tiny gaps = fragments of the same written value)."""
    out = list(group)
    changed = True
    while changed:
        changed = False
        for w in page_words:
            r = pymupdf.Rect(w[:4])
            if any(overlaps(r, o) for o in out + already):
                continue
            for o in out:
                same_line = r.y0 < o.y1 and r.y1 > o.y0
                gap = min(abs(r.x0 - o.x1), abs(o.x0 - r.x1))
                if same_line and gap < o.height * 0.45:
                    out.append(r)
                    changed = True
                    break
    return out


def deidentify_pdf(src: Path, dst: Path, known: dict[str, str], token: str,
                   alias: str, report: dict, rel: Path, name_rx: list[re.Pattern],
                   initials_map: dict[str, str], canonical: dict[str, str] | None = None,
                   vision_detect=None):
    canonical = canonical or {}
    doc = pymupdf.open(src)
    replaced = 0
    flags: list[str] = []

    for page in doc:
        # AcroForm fields first: their values live outside the page content
        # stream, so redactions alone won't touch them.
        for widget in page.widgets() or []:
            val = widget.field_value
            if isinstance(val, str) and val.strip():
                new = scrub_string(val, known, name_rx, alias)
                if new != val:
                    widget.field_value = new
                    widget.update()
                    replaced += 1

        # OCR treatment for any page whose visible text the text layer cannot
        # account for: no text at all (scan, vector line art, or a font with
        # no usable encoding), or a text layer UNDER a page-sized scan image
        # (searchable fax: replacing the invisible text leaves the visible
        # pixels intact). Native digital pages keep the redaction path.
        native_text = page.get_text().strip()
        big_scan = any(
            abs(r) >= 0.55 * abs(page.rect)
            for im in page.get_images(full=True)
            for r in page.get_image_rects(im[0]))
        ocr_page = not native_text or big_scan
        # Scanned pages iterate wipe -> re-OCR -> wipe: OCR output varies with
        # resolution, so a second read at another dpi catches stragglers the
        # first pass segmented differently. Surrogate text overlays are drawn
        # only AFTER the last pass, so re-OCR never re-reads a fake value.
        # A dpi of 0 means "use the page's own text layer" (searchable faxes:
        # their invisible OCR layer is often better than our re-OCR).
        wiped: list[pymupdf.Rect] = []
        overlays: list[tuple[pymupdf.Rect, str]] = []
        ocr_failed = False
        first_textpage = None  # the 300-dpi read: most reliable geometry
        if not ocr_page:
            dpis: tuple[int, ...] = (0,)
        elif native_text:
            dpis = (0, 300, 200, 400, 150)
        else:
            dpis = (300, 200, 400, 150)
        for dpi in dpis:
            textpage = None
            if dpi:
                try:
                    textpage = page.get_textpage_ocr(dpi=dpi, full=True)
                except (RuntimeError, ValueError) as exc:
                    flags.append(f"p{page.number + 1}: OCR unavailable ({exc}) - "
                                 f"page NOT fully de-identified, must be reviewed")
                    ocr_failed = True
                    break
                if first_textpage is None:
                    first_textpage = textpage
            text = page.get_text(textpage=textpage)
            if not text.strip():
                break

            jobs = collect_page_jobs(text, known, name_rx)
            page_words = page.get_text("words", textpage=textpage)
            widget_rects = [pymupdf.Rect(w.rect) for w in page.widgets() or []]
            groups: list[tuple[list[pymupdf.Rect], str]] = []
            placed: list[pymupdf.Rect] = []
            for literal, replacement in sorted(jobs.items(), key=lambda kv: -len(kv[0])):
                replacement = replacement.replace("{ALIAS}", alias)
                for group in locate_literal(page, textpage, literal, page_words):
                    if any(overlaps(r, p) for r in group for p in placed + wiped):
                        continue
                    # a form widget already renders this value (scrubbed above);
                    # drawing page-level text too would double-print
                    if any(overlaps(group[0], wr) for wr in widget_rects):
                        continue
                    if ocr_page:
                        # OCR segmentation can split one written value into
                        # fragments ("EMILY M" + "ARTIN"); pull in adjacent
                        # same-line fragments so no tail survives the wipe
                        group = _expand_adjacent(group, page_words, placed + wiped)
                    groups.append((group, replacement))
                    placed.extend(group)
            if not ocr_page:
                # patient initials (name-derived avatar badges on digital pages
                # only): exact word match, so "LAB"/blood types stay intact
                for x0, y0, x1, y1, word, *_ in page_words:
                    if word in initials_map:
                        rect = pymupdf.Rect(x0, y0, x1, y1)
                        if not any(overlaps(rect, p) for p in placed + wiped):
                            groups.append(([rect], initials_map[word]))
                            placed.append(rect)
            replaced += len(groups)
            wiped.extend(placed)

            if not ocr_page:
                if groups:
                    # redactions only ERASE; the replacement is drawn afterwards
                    # with insert_text at the exact matched font/size (redaction
                    # replacement text gets auto-shrunk to fit its box and ends
                    # up visibly smaller than the surrounding text)
                    draws = []
                    for group, replacement in groups:
                        line_rect = pymupdf.Rect(group[0])
                        for r in group[1:]:
                            if r.y0 < group[0].y1 and r.y1 > group[0].y0:
                                line_rect |= r
                        fontname, fontsize = match_font(page, line_rect, replacement)
                        # overflow may not collide with a neighboring word:
                        # shrink to the exact rect if one sits just right of us
                        neighbor = any(
                            w[0] > line_rect.x1 - 1 and w[0] < line_rect.x1 + line_rect.width * 0.2
                            and w[1] < line_rect.y1 and w[3] > line_rect.y0
                            for w in page_words)
                        if neighbor:
                            while fontsize > 4 and pymupdf.get_text_length(
                                    replacement, fontname=fontname,
                                    fontsize=fontsize) > line_rect.width:
                                fontsize *= 0.94
                        for rect in group:
                            page.add_redact_annot(rect, fill=(1, 1, 1))
                        draws.append((line_rect, replacement, fontname, fontsize))
                    page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE)
                    for line_rect, txt, fontname, fontsize in draws:
                        page.insert_text(
                            (line_rect.x0, line_rect.y1 - fontsize * 0.22), txt,
                            fontname=fontname, fontsize=fontsize,
                            color=(0, 0, 0), overlay=True)
            elif groups:
                # PHI pixels are wiped once, after all OCR attempts: repeated
                # replace_image calls stack copies of the scan and can corrupt
                # the page, so the rects are only accumulated here
                overlays.extend((g[0], repl) for g, repl in groups)
            # no early exit: wiping is deferred, so every dpi pass is a pure
            # detection union and each can catch words the others misread

        if ocr_page and (not ocr_failed or wiped):
            # identifiers 16/17: faces and signature handwriting - auto-blank + flag
            faces: list[pymupdf.Rect] = []
            sigs: list[pymupdf.Rect] = []
            bands: list[pymupdf.Rect] = []
            critical_bands: list[pymupdf.Rect] = []
            refills: list[tuple[pymupdf.Rect, str]] = []
            try:
                from deid.images import (CRITICAL_LABELS, detect_faces,
                                         labeled_value_regions, signature_regions)
                faces = detect_faces(page)
                sigs = signature_regions(page, first_textpage) if first_textpage else []
                for label, band in (labeled_value_regions(page, first_textpage)
                                    if first_textpage else []):
                    if label in CRITICAL_LABELS:
                        # name/DOB fields: ALWAYS wipe the band (OCR misreads of
                        # handwriting leave tails and garbage) and refill with
                        # the canonical fake value
                        bands.append(band)
                        critical_bands.append(band)
                        if canonical.get(label):
                            refills.append((band, canonical[label]))
                    elif not any(overlaps(band, r) for r in wiped):
                        bands.append(band)
                        flags.append(f"p{page.number + 1}: unreadable value after "
                                     f"'{label}' label blanked - confirm")
            except Exception as exc:
                flags.append(f"p{page.number + 1}: face/signature pass failed ({exc})")
            # ink OCR could not fully read (handwriting/signatures/logos):
            # locate the components locally, then ask the vision model per crop
            # whether each carries identifying information. Components are NOT
            # skipped for overlapping earlier wipes - OCR boxes on handwriting
            # rarely cover the full ink extent, and tails would survive.
            if vision_detect is not None:
                try:
                    from deid.images import unrecognized_ink_components
                    comps = unrecognized_ink_components(page, first_textpage)
                    hw = 0
                    for comp in comps:
                        if any(overlaps(comp, b) for b in bands):
                            continue
                        if vision_detect(page, comp):
                            bands.append(comp)
                            hw += 1
                    if hw:
                        flags.append(f"p{page.number + 1}: {hw} unreadable-ink "
                                     f"region(s) with PHI blanked by vision check")
                except Exception as exc:
                    flags.append(f"p{page.number + 1}: vision check failed ({exc})")
            # fax banner strip: transmission headers carry a date/time, phone
            # and sender in a dotted fax font OCR reads unreliably - wipe the
            # whole strip and re-type its scrubbed text instead
            banner_redraw = None
            if first_textpage is not None:
                strip = pymupdf.Rect(page.rect.x0, page.rect.y0, page.rect.x1,
                                     page.rect.y0 + min(30.0, page.rect.height * 0.05))
                strip_words = sorted(
                    (w for w in page.get_text("words", textpage=first_textpage)
                     if w[1] < strip.y1), key=lambda w: w[0])
                strip_text = " ".join(w[4] for w in strip_words)
                if re.search(r"(?i)\bfax\b", strip_text) and re.search(r"\d{4}", strip_text):
                    bands.append(strip)
                    critical_bands.append(strip)  # overlays there are replaced too
                    banner_redraw = scrub_string(strip_text, known, name_rx, alias)
                    flags.append(f"p{page.number + 1}: fax banner strip rewritten")
            wipe_rects = wiped + faces + sigs + bands
            wiped_ok = False
            if wipe_rects:
                # single background-fill wipe in RENDER space, replacing the
                # whole page content (kills scan pixels, vector text and any
                # invisible text layer at once); white boxes are the fallback
                try:
                    from deid.images import wipe_page_render
                    wiped_ok = wipe_page_render(page, wipe_rects, dpi=200)
                except Exception:
                    wiped_ok = False
                if not wiped_ok:
                    for rect in wipe_rects:
                        page.add_redact_annot(rect, fill=(1, 1, 1))
                    page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_PIXELS)
                if faces:
                    flags.append(f"p{page.number + 1}: {len(faces)} face region(s) "
                                 f"auto-blanked - confirm")
                if sigs:
                    flags.append(f"p{page.number + 1}: {len(sigs)} signature band(s) "
                                 f"auto-blanked - confirm")
            # overlays: drop any inside an always-wiped band (the canonical
            # refill replaces them) and merge near-duplicates from different
            # OCR resolutions
            final_overlays: list[tuple[pymupdf.Rect, str]] = []
            for rect, txt in overlays:
                if any(rect.intersects(b) for b in critical_bands):
                    continue  # the canonical refill replaces these
                if any(rect.intersects(r2) and t2 == txt for r2, t2 in final_overlays):
                    continue
                final_overlays.append((rect, txt))
            for band, txt in refills:
                fs = max(6.0, min(band.height * 0.5, 11.0))
                page.insert_text((band.x0 + 4, band.y0 + band.height * 0.62), txt,
                                 fontsize=fs, color=(0.05, 0.05, 0.05), overlay=True)
            if banner_redraw:
                page.insert_text((page.rect.x0 + 20, page.rect.y0 + 15),
                                 banner_redraw[:200], fontsize=7,
                                 color=(0.15, 0.15, 0.15), overlay=True)
            for rect, txt in final_overlays:
                fs = max(5.0, min(rect.height * 0.78, 13.0))
                page.insert_text((rect.x0, rect.y1 - rect.height * 0.18), txt,
                                 fontsize=fs, color=(0, 0, 0), overlay=True)
            if not wiped_ok:
                # content not already replaced by the render wipe (fallback
                # white boxes, or nothing to wipe): flatten so no original
                # text/image object survives in the file
                try:
                    from deid.images import flatten_page
                    flatten_page(page, dpi=200)
                except Exception as exc:
                    flags.append(f"p{page.number + 1}: flatten failed ({exc})")
            flags.append(f"p{page.number + 1}: scanned page de-identified via OCR "
                         f"- manual QA recommended for residual handwriting/photos")

        # hyperlink URIs can smuggle PHI in query strings; drop every link
        for link in page.get_links():
            page.delete_link(link)
        if not ocr_page and page.get_images(full=True):
            flags.append(f"p{page.number + 1}: contains image(s) - check for faces/handwriting")

    # document metadata leaks names (Author), care dates (CreationDate) and
    # workstation details; wipe /Info and the XMP metadata stream entirely.
    # set_metadata merges, so blank every standard key explicitly first.
    doc.set_metadata({k: "" for k in ("author", "title", "subject", "keywords",
                                      "creator", "producer", "creationDate", "modDate")})
    doc.set_metadata({"title": f"De-identified record - {token}",
                      "producer": "deidentify_patient_docs (HIPAA Safe Harbor)"})
    try:
        doc.del_xml_metadata()
    except AttributeError:
        doc.xref_set_key(doc.pdf_catalog(), "Metadata", "null")

    dst.parent.mkdir(parents=True, exist_ok=True)
    # garbage=4 also deduplicates identical streams (replace_image can leave a
    # second reference to the inpainted scan)
    doc.save(dst, garbage=4, deflate=True)
    doc.close()
    report["files"][str(rel)] = {
        "output": str(dst),
        "replacements": replaced,
        "flags": flags,
    }
    return replaced, flags


def shift_filename_dates(name: str, *, compact_only: bool = False) -> str:
    """Shift filename-shaped dates. With compact_only=True, slash/dash forms
    are left alone - callers that ALSO run scrub_string() must use this mode,
    or the generic date patterns would shift those dates a second time."""
    def sub_sep(m):
        try:
            dt = datetime(int(m.group(3)), int(m.group(1)), int(m.group(2)))
        except ValueError:
            return m.group(0)
        s = dt + timedelta(days=DATE_OFFSET)
        sep = m.group(0)[len(m.group(1))]
        return f"{s.month:02d}{sep}{s.day:02d}{sep}{s.year}"

    def sub_ymd(m):
        try:
            dt = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return m.group(0)
        s = dt + timedelta(days=DATE_OFFSET)
        return f"{s.year}{s.month:02d}{s.day:02d}"

    def sub_mdy(m):
        try:
            dt = datetime(int(m.group(3)), int(m.group(1)), int(m.group(2)))
        except ValueError:
            return m.group(0)
        s = dt + timedelta(days=DATE_OFFSET)
        return f"{s.month:02d}{s.day:02d}{s.year}"

    def sub_us2(m):  # underscore dates with 2-digit year: "7_25_26"
        yy = int(m.group(3))
        try:
            dt = datetime(1900 + yy if yy >= 70 else 2000 + yy,
                          int(m.group(1)), int(m.group(2)))
        except ValueError:
            return m.group(0)
        s = dt + timedelta(days=DATE_OFFSET)
        return f"{s.month}_{s.day}_{s.year % 100:02d}"

    seps = "_" if compact_only else "_\\-/"
    name = re.sub(rf"(?<!\d)(\d{{1,2}})[{seps}](\d{{1,2}})[{seps}]((?:19|20)\d{{2}})(?!\d)",
                  lambda m: sub_sep(m), name)
    name = re.sub(r"(?<!\d)((?:19|20)\d{2})([01]\d)([0-3]\d)(?!\d)", sub_ymd, name)
    name = re.sub(r"(?<!\d)([01]\d)([0-3]\d)((?:19|20)\d{2})(?!\d)", sub_mdy, name)
    name = re.sub(r"(?<!\d)(\d{1,2})_(\d{1,2})_(\d{2})(?!\d)", sub_us2, name)
    return name


def sanitize_filename(name: str, name_parts: list[str], persona: dict,
                      id_map: dict[str, str], *, compact_dates: bool = False) -> str:
    out = name
    for value, surrogate in id_map.items():
        out = re.sub(rf"(?<!\d){re.escape(value)}(?!\d)", surrogate, out)
    alias_file = f"{persona['first']} {persona['last']}"
    if len(name_parts) == 2:  # "Butler_Alva", "BUTLER, ALVA", ... -> persona
        f, l = (re.escape(p) for p in name_parts)
        out = re.sub(rf"(?:{f}|{l})[ ,_.\-]+(?:{f}|{l})", alias_file, out,
                     flags=re.IGNORECASE)
        out = re.sub(f, persona["first"], out, flags=re.IGNORECASE)
        out = re.sub(l, persona["last"], out, flags=re.IGNORECASE)
    return shift_filename_dates(out, compact_only=compact_dates)


def load_or_init_key(key_path: Path, display: str, gender: str, folder: Path,
                     taken: set[str]) -> dict:
    if key_path.exists():
        return json.loads(key_path.read_text())
    seed = secrets.randbits(48)
    rng = random.Random(seed)
    # persona full names must be unique per output root, or two patients
    # would merge into one bundle folder
    for attempt in range(100):
        first = rng.choice(FIRST_NAMES.get(gender, FIRST_NAMES["M"]))
        last = rng.choice(LAST_NAMES)
        if attempt >= 30:
            last = f"{last}-{rng.choice(LAST_NAMES)}"
        if f"{first} {last}" not in taken:
            break
    city, zc = rng.choice(FL_CITIES)
    # always shift into the past: a future date of death or visit would
    # immediately mark the record as synthetic (and confuse reviewers)
    offset = -rng.randint(60, 364)
    return {
        "WARNING": "Re-identification key. Store separately from the "
                   "de-identified documents. Do not distribute.",
        "token": new_token(),
        "patient": display,
        "source_folder": str(folder),
        "seed": seed,
        "date_offset_days": offset,
        "age_jitter_years": rng.choice([-1, 1]) * rng.randint(2, 3),
        "persona": {
            "first": first, "last": last,
            "street": f"{rng.randint(100, 9899)} {rng.choice(STREET_WORDS)} "
                      f"{rng.choice(STREET_SUFFIX)}",
            "city": city, "zip": zc,
            "email": f"{first.lower()}.{last.lower()}{rng.randint(10, 99)}@example.com",
        },
        "surrogates": {},
    }


def _enable_provider_patterns() -> None:
    """Idempotent: called from main() and from spawned workers."""
    if PROVIDER_ID_PATTERNS[0] not in GENERIC_PATTERNS:
        GENERIC_PATTERNS.extend(PROVIDER_ID_PATTERNS)


def process_patient(folder: Path, args: argparse.Namespace) -> None:
    """De-identify one patient folder end to end.

    Self-contained per-patient unit: all module-level state (surrogate store,
    persona, date offset) is (re)set here, so independent patients may run in
    separate PROCESSES - never threads, the globals would collide. The persona
    key file must already exist when running in parallel (main() pre-assigns
    them sequentially to keep persona names unique)."""
    global S, PERSONA, DATE_OFFSET, AGE_JITTER
    if args.scrub_providers:
        _enable_provider_patterns()

    known_ph, display, name_parts, name_rx, id_map, gender = \
        harvest_phi(folder, scrub_staff=args.scrub_providers,
                    scrub_facilities=not args.keep_facilities)
    slug = re.sub(r"[^a-z0-9]+", "-", display.lower()).strip("-")

    key_path = args.keys / f"{slug}.json"
    key = load_or_init_key(key_path, display, gender, folder, set())
    token, PERSONA = key["token"], dict(key["persona"])
    if "age_jitter_years" not in key:  # older key files: derive from seed
        rng = random.Random(key["seed"] ^ 0xA6E)
        key["age_jitter_years"] = rng.choice([-1, 1]) * rng.randint(2, 3)
    AGE_JITTER = key["age_jitter_years"]
    DATE_OFFSET = key["date_offset_days"]
    PERSONA["nominal_year"] = datetime.now().year
    S = SurrogateStore(key.get("surrogates", {}), key["seed"])

    known = finalize_known(known_ph, PERSONA, name_parts)
    id_map = {v: fake_id(v) for v in id_map}
    if args.scrub_providers:
        for v, fake in discover_providers(folder).items():
            known.setdefault(v, fake)

    llm_review: list[dict] = []
    llm_flags: list[str] = []
    if not args.no_llm:
        from deid.llm_detect import detect_phi_for_folder

        def surrogate_for(category: str, value: str) -> str | None:
            if category in ("person", "provider") and name_parts:
                # The LLM sometimes returns the patient's own name wrapped
                # in an honorific ("Mr Khojagul Zadran"), which misses the
                # known-value map; minting a random person here would give
                # the patient a second identity in the same bundle.
                m = re.match(r"\s*(?:mr|mrs|ms|miss)\b\.?\s*", value,
                             re.IGNORECASE)
                core = value[m.end():] if m else value
                toks = {t for t in re.split(r"[^A-Za-z]+", core.lower())
                        if len(t) > 1}
                if toks and toks <= {p.lower() for p in name_parts}:
                    prefix = value[:m.end()] if m else ""
                    return prefix + render_name(core, PERSONA, name_parts)
            factories = {
                "person": fake_person, "provider": fake_person,
                "org": fake_org, "street": fake_street, "city": fake_city,
                "zip": fake_zip, "date": fake_date, "phone": fake_phone,
                "email": fake_email, "ssn": fake_ssn, "id": fake_id,
                "url": lambda _v: "https://www.example.com",
                "ip": lambda _v: "203.0.113.7",
            }
            fn = factories.get(category)
            return fn(value) if fn else None

        additions, llm_review, llm_flags = detect_phi_for_folder(
            folder, cache=key.setdefault("llm_cache", {}),
            keep_providers=not args.scrub_providers,
            keep_facilities=args.keep_facilities,
            surrogate_for=surrogate_for)
        for v, replacement in additions.items():
            known.setdefault(v, replacement)
        for fl in llm_flags:
            print(f"  ! {fl}")
        print(f"  LLM detection: +{len(additions)} values, "
              f"{len(llm_review)} review items")

    alias = f"{PERSONA['last']}, {PERSONA['first']}"
    # canonical fake values for always-wiped labeled fields on scans
    canonical = {"patient name": f"{PERSONA['first']} {PERSONA['last']}",
                 "name": f"{PERSONA['first']} {PERSONA['last']}"}
    dob_variants = [v for v, ph in known_ph.items() if ph == "{DATE}"
                    and re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", v)]
    if dob_variants:
        dob_str = fake_dob(dob_variants[0])
        canonical.update({"dob": dob_str, "date of birth": dob_str,
                          "birth date": dob_str})

    vision_cb = None
    if not args.no_llm:
        from deid.vision_qa import make_handwriting_classifier
        vision_cb = make_handwriting_classifier(
            cache=key.setdefault("llm_cache", {}),
            include_orgs=not args.keep_facilities)

    initials_map = {}
    if len(name_parts) == 2:
        rf, rl = (p[0].upper() for p in name_parts)
        pf, pl = PERSONA["first"][0].upper(), PERSONA["last"][0].upper()
        initials_map = {rf + rl: pf + pl, rl + rf: pl + pf}

    out_dir = args.output / f"{PERSONA['first']} {PERSONA['last']}"
    report = {"root": str(folder), "files": {}}
    total = 0
    print(f"\n{display}  ->  {PERSONA['first']} {PERSONA['last']}  ({token}, "
          f"dates shifted {DATE_OFFSET:+d} days)")
    print(f"  known identifier values: {len(known)}")

    for pdf in sorted(folder.rglob("*.pdf")):
        rel = pdf.relative_to(folder)
        new_parts = [sanitize_filename(p, name_parts, PERSONA, id_map)
                     for p in rel.parts]
        dst = out_dir.joinpath(*new_parts)
        n, flags = deidentify_pdf(pdf, dst, known, token, alias, report,
                                  rel, name_rx, initials_map,
                                  canonical=canonical, vision_detect=vision_cb)
        total += n
        print(f"  {rel}  ({n} replacements)")
        for fl in flags:
            print(f"      ! {fl}")

    # sidecar JSONs: same crosswalk, so PDFs and JSONs stay consistent
    from deid.json_deid import audit_json_output, deidentify_jsons

    def _sanitize_json_name(name: str) -> str:
        out = sanitize_filename(name, name_parts, PERSONA, id_map)
        if name == name.lower():  # keep slug-style filenames slug-style
            out = re.sub(r"[ ,]+", "-", out.lower()).replace("--", "-")
        return out

    real_slug = f"{name_parts[1]}-{name_parts[0]}".lower() if len(name_parts) == 2 else ""
    fake_slug = f"{PERSONA['last']}-{PERSONA['first']}".lower()
    json_results = deidentify_jsons(
        folder, out_dir,
        scrub=lambda s: scrub_string(s, known, name_rx, alias),
        fake_id=fake_id, id_map=id_map,
        slug_pair=(real_slug, fake_slug),
        known_ids={v for v in known if v.isdigit()},
        sanitize_name=_sanitize_json_name,
        sanitize_text=lambda s: sanitize_filename(s, name_parts, PERSONA, id_map,
                                                  compact_dates=True),
        age_jitter=AGE_JITTER,
    )
    json_residuals = {}
    for src_name, info in json_results.items():
        hits = audit_json_output(Path(info["output"]), list(known))
        if hits:
            json_residuals[src_name] = hits
        print(f"  {src_name} -> {Path(info['output']).name}"
              + (f"  !! RESIDUAL: {hits[:5]}" if hits else ""))
    report["files"].update(json_results)

    args.keys.mkdir(parents=True, exist_ok=True)
    key["surrogates"] = S.map
    key["generated"] = datetime.now().isoformat(timespec="seconds")
    key["values_replaced"] = known
    key_path.write_text(json.dumps(key, indent=2))

    (out_dir / "_deid_report.json").write_text(json.dumps({
        "subject_alias": f"{PERSONA['first']} {PERSONA['last']}",
        "token": token,
        "method": "HIPAA Safe Harbor 164.514(b)(2), realistic surrogate "
                  "replacement with uniform date shifting",
        "total_replacements": total,
        "files": report["files"],
        "llm_detection": ("skipped (--no-llm)" if args.no_llm else "enabled"),
        "llm_review_items": llm_review,
        "llm_flags": llm_flags,
        "notes": [
            "All 18 Safe Harbor identifier categories replaced with "
            "consistent fabricated surrogates; no real PHI remains.",
            "Dates shifted by one secret per-patient offset (intervals "
            "preserved); ages >=90 aggregated to 90+.",
            "Provider/clinician names and NPIs retained (not patient "
            "identifiers under Safe Harbor).",
            "PDF metadata wiped, hyperlinks removed, form fields rewritten, "
            "scanned pages OCR-redacted.",
            "Pages flagged for manual QA may contain handwriting, photos or "
            "stylized facility logos OCR cannot read (identifiers 16/17; "
            "logos matter when facilities are scrubbed).",
        ],
    }, indent=2))
    print(f"  total: {total} replacements  ->  {out_dir}/")
    print(f"  key:   {key_path}  (store separately!)")


def _worker(folder: str, opts: dict) -> str:
    """One patient in a spawned process, stdout captured, so the parent can
    print each patient's log as a single uninterleaved block."""
    import contextlib
    import io
    import traceback

    args = argparse.Namespace(**opts)
    for name in ("input", "output", "keys"):
        setattr(args, name, Path(getattr(args, name)))
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            process_patient(Path(folder), args)
        except Exception:
            traceback.print_exc(file=buf)
            print(f"!! FAILED: {folder}", file=buf)
    return buf.getvalue()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--input", default="patient_docs", type=Path)
    ap.add_argument("--output", default="patient_docs_deid", type=Path)
    ap.add_argument("--keys", default="deid_keys", type=Path,
                    help="Where the re-identification crosswalk is written. "
                         "Store separately from --output; never distribute together.")
    ap.add_argument("--scrub-providers", action="store_true",
                    help="Also replace clinician/staff names, NPIs and PTANs with "
                         "surrogates (not required by Safe Harbor; off by default).")
    ap.add_argument("--keep-facilities", action="store_true",
                    help="Leave facility/organization names in place "
                         "(default replaces them with fake org names).")
    ap.add_argument("--no-llm", action="store_true",
                    help="Skip the Claude-based secondary PHI detection pass "
                         "(regex/harvest coverage only).")
    ap.add_argument("--workers", type=int, default=1,
                    help="De-identify up to N patients in parallel (separate "
                         "processes; default 1 = sequential).")
    ap.add_argument("--skip-existing", action="store_true",
                    help="Skip patients whose de-identified bundle already has "
                         "a _deid_report.json (resume an interrupted batch).")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(line_buffering=True)  # live progress through pipes
    except AttributeError:
        pass

    if args.scrub_providers:
        _enable_provider_patterns()

    if not args.input.is_dir():
        print(f"error: input folder not found: {args.input}", file=sys.stderr)
        return 1

    patient_dirs = [d for d in sorted(args.input.iterdir()) if d.is_dir()]
    if not patient_dirs:
        print(f"error: no patient folders inside {args.input}", file=sys.stderr)
        return 1

    taken_personas: set[str] = set()
    for existing in args.keys.glob("*.json") if args.keys.is_dir() else []:
        try:
            p = json.loads(existing.read_text()).get("persona", {})
            taken_personas.add(f"{p.get('first', '')} {p.get('last', '')}")
        except (json.JSONDecodeError, OSError):
            continue

    # Personas/keys are assigned SEQUENTIALLY before any worker starts: two
    # parallel workers could otherwise draw the same persona and their bundle
    # folders would merge. This loop also applies --skip-existing.
    work: list[Path] = []
    for folder in patient_dirs:
        _, display, _, _, _, gender = harvest_phi(
            folder, scrub_staff=args.scrub_providers,
            scrub_facilities=not args.keep_facilities)
        slug = re.sub(r"[^a-z0-9]+", "-", display.lower()).strip("-")
        key_path = args.keys / f"{slug}.json"
        is_new = not key_path.exists()
        key = load_or_init_key(key_path, display, gender, folder, taken_personas)
        persona = f"{key['persona']['first']} {key['persona']['last']}"
        taken_personas.add(persona)
        if is_new:
            args.keys.mkdir(parents=True, exist_ok=True)
            key_path.write_text(json.dumps(key, indent=2))
        if args.skip_existing and (args.output / persona
                                   / "_deid_report.json").exists():
            print(f"skipping {display} -> {persona} (bundle already exists)")
            continue
        work.append(folder)

    if args.workers > 1 and len(work) > 1:
        from concurrent.futures import ProcessPoolExecutor, as_completed

        opts = dict(vars(args))
        for name in ("input", "output", "keys"):
            opts[name] = str(opts[name])
        print(f"running {len(work)} patients across "
              f"{min(args.workers, len(work))} worker processes")
        with ProcessPoolExecutor(max_workers=min(args.workers, len(work))) as pool:
            futures = {pool.submit(_worker, str(f), opts): f for f in work}
            for fut in as_completed(futures):
                print(fut.result(), end="", flush=True)
    else:
        for folder in work:
            process_patient(folder, args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
