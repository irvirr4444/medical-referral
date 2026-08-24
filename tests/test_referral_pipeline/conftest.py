from __future__ import annotations

import sys
from pathlib import Path

import pytest

_MONDAY_DIR = Path(__file__).resolve().parents[2] / "src" / "monday.com"
if str(_MONDAY_DIR) not in sys.path:
    sys.path.insert(0, str(_MONDAY_DIR))


@pytest.fixture(autouse=True)
def use_local_review_store(monkeypatch):
    monkeypatch.setenv("REFERRAL_REVIEW_STORE", "sqlite")
    monkeypatch.setenv("WORKFLOW_DATABASE_BACKEND", "sqlite")
    monkeypatch.delenv("WORKFLOW_READ_EXISTING_REMOTE", raising=False)

