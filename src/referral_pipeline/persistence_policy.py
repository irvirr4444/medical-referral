"""Fail-closed rules for persisting referral data outside the local machine."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path


DEFAULT_SYNTHETIC_MANIFEST = Path("output/pdf/synthetic-referrals/dataset.json")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class SyntheticPersistencePolicy:
    """Allow remote persistence only for hashes in a synthetic dataset manifest."""

    allowed_sha256: frozenset[str]
    manifest_path: Path

    @classmethod
    def from_environment(cls) -> "SyntheticPersistencePolicy":
        configured = os.getenv("SYNTHETIC_DATASET_MANIFEST", "").strip()
        return cls.from_manifest(Path(configured) if configured else DEFAULT_SYNTHETIC_MANIFEST)

    @classmethod
    def from_manifest(cls, path: str | Path) -> "SyntheticPersistencePolicy":
        manifest_path = Path(path)
        if not manifest_path.is_file():
            return cls(frozenset(), manifest_path)

        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls(frozenset(), manifest_path)

        if not isinstance(payload, dict) or payload.get("synthetic_only") is not True:
            return cls(frozenset(), manifest_path)

        cases = payload.get("cases")
        if not isinstance(cases, list):
            return cls(frozenset(), manifest_path)

        hashes = {
            str(case.get("sha256") or "").strip().casefold()
            for case in cases
            if isinstance(case, dict)
        }
        return cls(frozenset(value for value in hashes if _SHA256.fullmatch(value)), manifest_path)

    def permits(self, attachment_sha256: str | None) -> bool:
        digest = str(attachment_sha256 or "").strip().casefold()
        return bool(_SHA256.fullmatch(digest) and digest in self.allowed_sha256)

    def stage_one_backend(self, requested_backend: str, attachment_sha256: str | None) -> str:
        """Keep unknown referrals local even when the service uses Supabase."""
        backend = requested_backend.strip().casefold()
        if backend != "supabase":
            return backend
        return "supabase" if self.permits(attachment_sha256) else "sqlite"
