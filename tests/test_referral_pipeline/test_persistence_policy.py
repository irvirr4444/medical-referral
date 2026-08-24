from __future__ import annotations

import hashlib
import json

from referral_pipeline.persistence_policy import SyntheticPersistencePolicy
from referral_pipeline.review.store import ReviewStore, build_review_store


def _manifest(tmp_path, content: bytes):
    digest = hashlib.sha256(content).hexdigest()
    path = tmp_path / "dataset.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "synthetic_only": True,
                "cases": [{"filename": "SYNTHETIC-case.pdf", "sha256": digest}],
            }
        ),
        encoding="utf-8",
    )
    return path, digest


def test_only_manifest_hashes_are_allowed_for_supabase(tmp_path) -> None:
    path, digest = _manifest(tmp_path, b"synthetic referral")
    policy = SyntheticPersistencePolicy.from_manifest(path)

    assert policy.permits(digest)
    assert policy.stage_one_backend("supabase", digest) == "supabase"
    assert policy.stage_one_backend("supabase", "0" * 64) == "sqlite"
    assert policy.stage_one_backend("sqlite", "0" * 64) == "sqlite"


def test_missing_or_unmarked_manifest_fails_closed(tmp_path) -> None:
    missing = SyntheticPersistencePolicy.from_manifest(tmp_path / "missing.json")
    assert not missing.permits("0" * 64)

    path = tmp_path / "dataset.json"
    path.write_text(json.dumps({"synthetic_only": False, "cases": []}), encoding="utf-8")
    unmarked = SyntheticPersistencePolicy.from_manifest(path)
    assert not unmarked.permits("0" * 64)


def test_review_store_can_be_forced_local_even_with_supabase_configured(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("REFERRAL_REVIEW_STORE", "supabase")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-key")

    store = build_review_store(tmp_path / "state.sqlite", allow_supabase=False)

    assert isinstance(store, ReviewStore)
