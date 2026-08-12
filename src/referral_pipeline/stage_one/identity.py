"""Opaque, deterministic identifiers shared by inbox, worker, and UI."""

from __future__ import annotations

import hashlib


def source_ref(message_id: str, attachment_id: str) -> str:
    identity = f"{message_id}\0{attachment_id}".encode("utf-8")
    return hashlib.sha256(identity).hexdigest()[:16]


def case_id_for_source(message_id: str, attachment_id: str) -> str:
    return f"case_{source_ref(message_id, attachment_id)}"
