from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ExtractedText:
    path: Path
    pages: list[str]

    @property
    def combined(self) -> str:
        return "\n\n".join(self.pages)


def extract_text(pdf_path: str | Path, *, max_pages: int | None = None) -> ExtractedText:
    """
    Extract text from a PDF's text layer using pdfplumber.

    `max_pages` caps pages read for cost/perf parity with the vision path.
    """
    import pdfplumber

    p = Path(pdf_path)
    pages_text: list[str] = []
    with pdfplumber.open(p) as pdf:
        n = len(pdf.pages)
        limit = n if max_pages is None else min(n, max_pages)
        for i in range(limit):
            txt = pdf.pages[i].extract_text() or ""
            pages_text.append(txt)
    return ExtractedText(path=p, pages=pages_text)

