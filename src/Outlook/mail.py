"""PDF-only attachment primitives shared by local and Outlook sources."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from email import policy
from email.utils import parsedate_to_datetime
from email.parser import BytesParser
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class InboundPdfAttachment:
    source: str
    message_id: str
    attachment_id: str
    filename: str
    content: bytes
    received_at: str | None = None
    subject: str | None = None
    sender: str | None = None

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content).hexdigest()

    @property
    def safe_filename(self) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(self.filename).name).strip("._")
        return cleaned or "referral.pdf"


def is_pdf_file(filename: str | None, content: bytes) -> bool:
    """Require both a PDF filename and file signature, not just a MIME label."""
    return bool(filename and filename.lower().endswith(".pdf") and content.lstrip().startswith(b"%PDF-"))


def read_eml_pdf_attachments(path: str | Path) -> list[InboundPdfAttachment]:
    """Read only genuine PDF attachments from a local RFC-822 email fixture."""
    file_path = Path(path)
    message = BytesParser(policy=policy.default).parsebytes(file_path.read_bytes())
    message_id = str(message.get("Message-ID") or file_path.stem)
    attachments: list[InboundPdfAttachment] = []
    for index, part in enumerate(message.iter_attachments()):
        filename = part.get_filename() or ""
        content = part.get_payload(decode=True) or b""
        if not is_pdf_file(filename, content):
            continue
        attachments.append(
            InboundPdfAttachment(
                source="eml-fixture",
                message_id=message_id,
                attachment_id=str(index),
                filename=filename,
                content=content,
                received_at=_message_date(message.get("Date")),
                subject=str(message.get("Subject") or "") or None,
                sender=_eml_sender(message.get("From")),
            )
        )
    return attachments


def materialize_attachments(attachments: Iterable[InboundPdfAttachment], output_dir: str | Path) -> list[tuple[InboundPdfAttachment, Path]]:
    """Persist accepted PDFs under a hash-derived run directory for reproducibility."""
    root = Path(output_dir)
    materialized: list[tuple[InboundPdfAttachment, Path]] = []
    for attachment in attachments:
        folder = root / attachment.sha256[:16]
        folder.mkdir(parents=True, exist_ok=True)
        destination = folder / attachment.safe_filename
        destination.write_bytes(attachment.content)
        materialized.append((attachment, destination))
    return materialized


def _message_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).isoformat()
    except (TypeError, ValueError, IndexError):
        return None


def _eml_sender(value: str | None) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    match = re.search(r"<([^>]+)>", text)
    address = (match.group(1) if match else text).strip().strip('"')
    return address or None
