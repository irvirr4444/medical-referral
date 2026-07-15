from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


class PopplerNotInstalledError(RuntimeError):
    pass


@dataclass(frozen=True)
class PdfInspection:
    path: Path
    page_count: int
    has_text_layer: bool


def get_page_count(pdf_path: str | Path) -> int:
    """
    Fast page counting using pypdfium2.

    We intentionally do not rely on Poppler for this since Poppler may be missing
    in dev environments; Poppler is required for pdftoppm rasterization in the
    actual extraction path, but counting pages should be cheap and reliable.
    """
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(str(pdf_path))
    return len(doc)


def _pdffonts_available() -> bool:
    try:
        subprocess.run(["pdffonts", "-h"], check=False, capture_output=True, text=True)
        return True
    except FileNotFoundError:
        return False


def has_text_layer(pdf_path: str | Path) -> bool:
    """
    Detect whether a PDF has a real text layer, via `pdffonts`.

    Heuristic: if `pdffonts` reports at least one font row, the PDF likely has
    selectable text (even if sparse). Scanned faxes typically report no fonts.
    """
    if not _pdffonts_available():
        raise PopplerNotInstalledError(
            "Poppler is required for text-layer detection. Install `pdffonts` (poppler-utils)."
        )

    proc = subprocess.run(["pdffonts", str(pdf_path)], check=False, capture_output=True, text=True)
    # pdffonts prints to stdout, errors to stderr. Treat non-zero as "unknown" not "no text".
    out = proc.stdout or ""
    # Typical header:
    # name type encoding emb sub uni object ID
    # ---------------------------------------
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    if len(lines) <= 2:
        return False

    # Consider any non-header row as a font row.
    non_header = []
    for ln in lines:
        if re.match(r"^name\s+type\s+encoding", ln):
            continue
        if re.match(r"^-{5,}$", ln):
            continue
        non_header.append(ln)
    return len(non_header) > 0


def inspect_pdf(pdf_path: str | Path) -> PdfInspection:
    p = Path(pdf_path)
    page_count = get_page_count(p)
    text_layer = has_text_layer(p)
    return PdfInspection(path=p, page_count=page_count, has_text_layer=text_layer)

