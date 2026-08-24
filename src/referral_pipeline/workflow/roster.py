"""Load the current case-manager choices without inventing territory rules."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def load_case_manager_roster(path: str | Path | None = None) -> list[dict[str, str]]:
    roster_path = Path(
        path
        or os.getenv("CASE_MANAGER_ROSTER_PATH")
        or Path(__file__).resolve().parents[3] / "case_managers.json"
    )
    payload = json.loads(roster_path.read_text(encoding="utf-8"))
    rows = payload.get("case_managers") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise ValueError("case-manager roster must contain a case_managers list")

    managers: dict[str, dict[str, str]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        email = _text(row.get("email")).casefold()
        name = _text(row.get("name"))
        if not email or "@" not in email or not name or name.casefold() == email:
            continue
        managers[email] = {"name": name, "email": email}
    return sorted(managers.values(), key=lambda manager: manager["name"].casefold())


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""
