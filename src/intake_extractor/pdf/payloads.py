from __future__ import annotations

import base64
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class PdfPayloadError(RuntimeError):
    pass


@dataclass(frozen=True)
class TextPage:
    page_number: int
    text: str


@dataclass(frozen=True)
class ExtractedText:
    pages: list[TextPage]


@dataclass(frozen=True)
class PageImage:
    page_number: int
    media_type: str
    base64_data: str


@dataclass(frozen=True)
class ExtractedImages:
    pages: list[PageImage]


def _pdffonts_available() -> bool:
    try:
        subprocess.run(["pdffonts", "-h"], check=False, capture_output=True, text=True)
        return True
    except FileNotFoundError:
        return False


def _pdftoppm_available() -> bool:
    try:
        subprocess.run(["pdftoppm", "-h"], check=False, capture_output=True, text=True)
        return True
    except FileNotFoundError:
        return False


def has_text_layer(pdf_path: str | Path) -> bool:
    if not _pdffonts_available():
        raise PdfPayloadError("Poppler `pdffonts` not found. Install poppler (pdffonts/pdftoppm).")

    proc = subprocess.run(["pdffonts", str(pdf_path)], check=False, capture_output=True, text=True)
    out = proc.stdout or ""
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    if len(lines) <= 2:
        return False
    non_header = []
    for line in lines:
        if re.match(r"^name\s+type\s+encoding", line):
            continue
        if re.match(r"^-{5,}$", line):
            continue
        non_header.append(line)
    return len(non_header) > 0


def extract_text(pdf_path: str | Path, *, max_pages: int | None = None) -> ExtractedText:
    import pdfplumber

    pages_text: list[TextPage] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        limit = len(pdf.pages) if max_pages is None else min(len(pdf.pages), max_pages)
        for index in range(limit):
            pages_text.append(TextPage(page_number=index + 1, text=pdf.pages[index].extract_text() or ""))
    return ExtractedText(pages=pages_text)


def _read_file_base64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def extract_images(pdf_path: str | Path, *, max_pages: int | None = None, dpi: int = 150) -> ExtractedImages:
    if not _pdftoppm_available():
        raise PdfPayloadError("Poppler `pdftoppm` not found. Install poppler (pdffonts/pdftoppm).")

    pdf = Path(pdf_path)
    with tempfile.TemporaryDirectory(prefix="intake_extractor_pdftoppm_") as temp_dir:
        out_prefix_path = Path(temp_dir) / "page"
        out_prefix = str(out_prefix_path)
        cmd: list[str] = ["pdftoppm", "-png", "-r", str(dpi), "-f", "1", str(pdf), out_prefix]
        if max_pages is not None:
            cmd[cmd.index(str(pdf)) : cmd.index(str(pdf))] = ["-l", str(max_pages)]
        subprocess.run(cmd, check=True, capture_output=True, text=True)

        produced = list(out_prefix_path.parent.glob(f"{out_prefix_path.name}-*.png"))
        if not produced:
            raise PdfPayloadError("pdftoppm produced no PNG files")

        def page_num(png_path: Path) -> int:
            try:
                return int(png_path.stem.split("-")[-1])
            except Exception:
                return 10**9

        images: list[PageImage] = []
        for png_path in sorted(produced, key=page_num):
            images.append(
                PageImage(
                    page_number=page_num(png_path),
                    media_type="image/png",
                    base64_data=_read_file_base64(png_path),
                )
            )
        return ExtractedImages(pages=images)


def vision_user_content(pages: list[PageImage]) -> list[dict[str, Any]]:
    page_numbers = [page.page_number for page in pages]
    content: list[dict[str, Any]] = [
        {"type": "text", "text": f"INPUT TYPE: IMAGES\nPAGES PROVIDED (in order): {', '.join(map(str, page_numbers))}\n"}
    ]
    for page in pages:
        content.append(
            {
                "type": "image",
                "source": {"type": "base64", "media_type": page.media_type, "data": page.base64_data},
            }
        )
    return content


def text_user_content(pages: list[TextPage]) -> list[dict[str, Any]]:
    page_numbers = [page.page_number for page in pages]
    chunks: list[str] = [f"INPUT TYPE: TEXT\nPAGES PROVIDED (actual page numbers): {', '.join(map(str, page_numbers))}\n"]
    for page in pages:
        chunks.append(f"\n--- PAGE {page.page_number} ---\n{page.text}\n")
    return [{"type": "text", "text": "\n".join(chunks)}]

