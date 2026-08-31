"""Unit tests for the sidecar-JSON de-identification walk."""

import json

from deid.json_deid import JsonDeidentifier, audit_json_output, deidentify_jsons


def make_deid(**overrides):
    kwargs = dict(
        scrub=lambda s: s.replace("Alva Butler", "Chester Stanton"),
        fake_id=lambda s: "9" * len(s),
        id_map={"270499": "133924"},
        slug_pair=("butler-alva", "stanton-chester"),
        known_ids={"55125"},
        sanitize_text=lambda s: s,
    )
    kwargs.update(overrides)
    return JsonDeidentifier(**kwargs)


def test_walk_scrubs_strings_and_drops_sha256():
    deid = make_deid()
    out = deid.walk({
        "name": "Alva Butler",
        "sha256": "abc123",
        "nested": [{"note": "seen Alva Butler today"}],
    })
    assert out == {"name": "Chester Stanton",
                   "nested": [{"note": "seen Chester Stanton today"}]}


def test_walk_replaces_known_and_keyed_ints():
    deid = make_deid()
    out = deid.walk({"patientId": 55125, "item_id": 123456,
                     "unrelated_count": 42, "encounter": 270499})
    assert out["patientId"] == 99999
    assert out["item_id"] == 999999
    assert out["unrelated_count"] == 42          # non-identifier int untouched
    assert out["encounter"] == 999999            # str form in id_map


def test_windows_username_and_slug_rewritten():
    deid = make_deid()
    s = deid._clean_string(r"C:\Users\maria\Desktop\butler-alva\encounter-270499.html")
    assert r"\maria\Desktop" not in s
    assert "stanton-chester" in s
    assert "133924" in s and "270499" not in s


def test_metadata_offsets_recomputed():
    deid = make_deid()
    data = {
        "source_pages": [{"page": 1, "text": "NAME: Chester Stanton visited."}],
        "entities": [{"type": "PATIENT_NAME", "value": "Chester Stanton",
                      "occurrences": [{"page": 1, "char_start": 0, "char_end": 5}]}],
    }
    deid.fix_metadata_offsets(data)
    occ = data["entities"][0]["occurrences"]
    assert occ == [{"page": 1, "char_start": 6, "char_end": 21}]


def test_deidentify_jsons_end_to_end(tmp_path):
    src_dir = tmp_path / "in"
    src_dir.mkdir()
    (src_dir / "butler-alva.activity.json").write_text(json.dumps(
        {"name": "Alva Butler", "sha256": "x", "patientId": 55125}))
    results = deidentify_jsons(
        src_dir, tmp_path / "out",
        scrub=lambda s: s.replace("Alva Butler", "Chester Stanton"),
        fake_id=lambda s: "9" * len(s),
        id_map={}, slug_pair=("butler-alva", "stanton-chester"),
        known_ids={"55125"},
        sanitize_name=lambda n: n.replace("butler-alva", "stanton-chester"),
        sanitize_text=lambda s: s,
    )
    out_path = tmp_path / "out" / "stanton-chester.activity.json"
    assert out_path.exists()
    data = json.loads(out_path.read_text())
    assert data == {"name": "Chester Stanton", "patientId": 99999}
    assert audit_json_output(out_path, ["Alva Butler", "55125"]) == []
    assert results["butler-alva.activity.json"]["flags"] == []
