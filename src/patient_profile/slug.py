"""Name slugs for the live patient profile URL."""

from __future__ import annotations

import re
import unicodedata


def slugify_patient_key(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug


def given_family_slug(value: str) -> str:
    trimmed = (value or "").strip()
    if not trimmed:
        return ""
    if "," in trimmed:
        family, given = trimmed.split(",", 1)
        return slugify_patient_key(f"{given} {family}")
    return slugify_patient_key(trimmed)


def search_names_from_slug(slug: str) -> tuple[str, str]:
    """Return (`Alva Butler`, `BUTLER, ALVA`) for a first-last slug."""
    tokens = [part for part in slugify_patient_key(slug).split("-") if part]
    if not tokens:
        raise ValueError("slug must contain at least one letter or number")
    if len(tokens) == 1:
        word = tokens[0].title()
        return word, word
    given = " ".join(part.title() for part in tokens[:-1])
    family = tokens[-1].title()
    return f"{given} {family}", f"{family.upper()}, {given.upper()}"
