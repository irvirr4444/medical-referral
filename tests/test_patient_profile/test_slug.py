from __future__ import annotations

from patient_profile.slug import given_family_slug, search_names_from_slug, slugify_patient_key


def test_given_family_slug_from_last_first_display_name() -> None:
    assert given_family_slug("Butler, Alva") == "alva-butler"
    assert given_family_slug("Alva Butler") == "alva-butler"
    assert slugify_patient_key("Butler, Alva") == "butler-alva"


def test_search_names_from_first_last_slug() -> None:
    assert search_names_from_slug("alva-butler") == ("Alva Butler", "BUTLER, ALVA")
    assert search_names_from_slug("butler-alva")[0] == "Butler Alva"
