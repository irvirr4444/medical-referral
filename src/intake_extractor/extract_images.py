from __future__ import annotations

import base64
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .pdf_inspect import PopplerNotInstalledError, get_page_count


DEFAULT_MAX_PAGES = 6


@dataclass(frozen=True)
class PageImage:
    page_number: int  # 1-indexed
    media_type: str  # e.g. "image/png"
    base64_data: str  # raw base64 (no data: prefix)


@dataclass(frozen=True)
class ExtractedImages:
    path: Path
    pages: list[PageImage]


def _pdftoppm_available() -> bool:
    try:
        subprocess.run(["pdftoppm", "-h"], check=False, capture_output=True, text=True)
        return True
    except FileNotFoundError:
        return False


def _read_file_base64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def extract_images(
    pdf_path: str | Path,
    *,
    max_pages: int = DEFAULT_MAX_PAGES,
    dpi: int = 150,
) -> ExtractedImages:
    """
    Rasterize a PDF into PNG images using `pdftoppm` (Poppler).

    Returns ALL selected pages as base64 PNGs in one object. This enables
    sending a whole packet as a single multi-image model request (not one call
    per page).
    """
    if not _pdftoppm_available():
        raise PopplerNotInstalledError(
            "Poppler is required for image extraction. Install `pdftoppm` (poppler-utils)."
        )

    p = Path(pdf_path)
    total_pages = get_page_count(p)
    pages_to_render = min(total_pages, max_pages)

    with tempfile.TemporaryDirectory(prefix="intake_extractor_pdftoppm_") as td:
        out_prefix_path = Path(td) / "page"
        out_prefix = str(out_prefix_path)
        # pdftoppm uses 1-indexed -f/-l.
        cmd = [
            "pdftoppm",
            "-png",
            "-r",
            str(dpi),
            "-f",
            "1",
            "-l",
            str(pages_to_render),
            str(p),
            out_prefix,
        ]
        subprocess.run(cmd, check=True, capture_output=True, text=True)

        images: list[PageImage] = []
        # Output naming varies by platform/version (e.g. page-1.png vs page-01.png).
        produced = list(out_prefix_path.parent.glob(f"{out_prefix_path.name}-*.png"))
        if not produced:
            raise RuntimeError("pdftoppm produced no PNG files")

        def _page_num(png_path: Path) -> int:
            # expected suffix: "<prefix>-<num>.png" where <num> may be zero-padded
            stem = png_path.stem  # e.g. "page-01"
            try:
                return int(stem.split("-")[-1])
            except Exception:
                return 10**9

        produced_sorted = sorted(produced, key=_page_num)
        for png_path in produced_sorted:
            num = _page_num(png_path)
            b64 = _read_file_base64(png_path)
            images.append(PageImage(page_number=num, media_type="image/png", base64_data=b64))

    return ExtractedImages(path=p, pages=images)

