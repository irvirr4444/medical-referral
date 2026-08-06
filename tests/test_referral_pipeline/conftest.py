from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def use_local_review_store(monkeypatch):
    monkeypatch.setenv("REFERRAL_REVIEW_STORE", "sqlite")

