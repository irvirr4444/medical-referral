from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, TypeVar


class _HasPageNumber(Protocol):
    page_number: int


TPage = TypeVar("TPage", bound=_HasPageNumber)


@dataclass(frozen=True)
class PageSelectionConfig:
    max_text_pages: int = 8
    max_vision_pages: int = 8
    first_page_bonus: float = 2.5
    keyword_weights: dict[str, float] = field(
        default_factory=lambda: {
            "referral": 4.0,
            "referred": 4.0,
            "order": 3.5,
            "ordered": 3.5,
            "referring": 3.5,
            "requested": 3.0,
            "service": 2.5,
            "home health": 3.0,
            "wound care": 3.0,
            "physical therapy": 2.5,
            "skilled nursing": 2.5,
            "patient": 1.5,
            "diagnosis": 2.0,
            "icd": 2.0,
            "insurance": 2.0,
            "provider": 2.0,
            "facility": 1.5,
            "dob": 1.5,
            "mrn": 1.5,
            "phone": 1.0,
            "fax": 1.0
        }
    )


DEFAULT_SELECTION_CONFIG = PageSelectionConfig()


def _compact_text(value: str) -> str:
    return " ".join(value.lower().split())


def select_text_pages(
    pages: list[TPage],
    *,
    max_pages: int | None,
    config: PageSelectionConfig = DEFAULT_SELECTION_CONFIG,
) -> list[TPage]:
    if not pages:
        return []

    cap = max_pages if max_pages is not None else config.max_text_pages
    if cap <= 0:
        return []
    if len(pages) <= cap:
        return pages

    scored: list[tuple[float, int, TPage]] = []
    for page in pages:
        page_text = _compact_text(getattr(page, "text", ""))
        score = 0.0
        if page.page_number == 1:
            score += config.first_page_bonus
        for keyword, weight in config.keyword_weights.items():
            if keyword in page_text:
                score += weight
        scored.append((score, page.page_number, page))

    selected = sorted(scored, key=lambda item: (-item[0], item[1]))[:cap]
    return sorted((page for _, _, page in selected), key=lambda page: page.page_number)


def select_image_pages(
    pages: list[TPage],
    *,
    max_pages: int | None,
    config: PageSelectionConfig = DEFAULT_SELECTION_CONFIG,
) -> list[TPage]:
    if not pages:
        return []

    cap = max_pages if max_pages is not None else config.max_vision_pages
    if cap <= 0:
        return []
    if len(pages) <= cap:
        return pages

    if cap >= 6 and len(pages) > cap:
        selected = pages[: cap - 1] + [pages[-1]]
        return sorted(selected, key=lambda page: page.page_number)
    return pages[:cap]
