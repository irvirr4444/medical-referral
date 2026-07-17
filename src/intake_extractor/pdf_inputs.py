from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .pdf_payloads import (
    PageImage,
    TextPage,
    extract_images,
    extract_text,
    has_text_layer,
    text_user_content,
    vision_user_content,
)
from .selection import DEFAULT_SELECTION_CONFIG, PageSelectionConfig, select_image_pages, select_text_pages


PdfInputMode = Literal["auto", "text", "image", "hybrid"]
ResolvedPdfInputMode = Literal["text", "image", "hybrid"]
PDF_INPUT_MODE_CHOICES: tuple[PdfInputMode, ...] = ("auto", "text", "image", "hybrid")


@dataclass(frozen=True)
class PdfInputPayload:
    requested_mode: PdfInputMode
    resolved_mode: ResolvedPdfInputMode
    user_content: list[dict[str, object]]
    pages_used: int
    selected_page_numbers: list[int]
    selected_text_pages: list[TextPage]
    selected_image_pages: list[PageImage]


def resolve_input_mode(requested_mode: PdfInputMode, *, pdf_has_text_layer: bool) -> ResolvedPdfInputMode:
    if requested_mode == "auto":
        return "text" if pdf_has_text_layer else "image"
    return requested_mode


def build_user_content_for_mode(
    *,
    resolved_mode: ResolvedPdfInputMode,
    text_pages: list[TextPage],
    image_pages: list[PageImage],
) -> list[dict[str, object]]:
    if resolved_mode == "text":
        return text_user_content(text_pages)
    if resolved_mode == "image":
        return vision_user_content(image_pages)

    page_numbers = _ordered_unique(page.page_number for page in text_pages + image_pages)
    content: list[dict[str, object]] = [
        {
            "type": "text",
            "text": (
                "INPUT TYPE: HYBRID\n"
                f"PAGES PROVIDED (actual page numbers): {', '.join(map(str, page_numbers))}\n"
                "The same PDF pages are provided both as extracted text and rendered page images. "
                "Use the visual layout to resolve section boundaries, headers, tables, handwriting, and sender blocks."
            ),
        }
    ]
    if text_pages:
        content.extend(text_user_content(text_pages))
    for page in image_pages:
        content.append(
            {
                "type": "image",
                "source": {"type": "base64", "media_type": page.media_type, "data": page.base64_data},
            }
        )
    return content


def build_pdf_input_payload(
    pdf_path: str | Path,
    *,
    input_mode: PdfInputMode = "auto",
    max_pages: int | None = None,
    selection_config: PageSelectionConfig = DEFAULT_SELECTION_CONFIG,
) -> PdfInputPayload:
    pdf = Path(pdf_path)
    resolved_mode = resolve_input_mode(input_mode, pdf_has_text_layer=has_text_layer(pdf))

    selected_text_pages: list[TextPage] = []
    selected_image_pages: list[PageImage] = []

    if resolved_mode in {"text", "hybrid"}:
        extracted_text = extract_text(pdf, max_pages=max_pages)
        selected_text_pages = (
            extracted_text.pages
            if max_pages is None
            else select_text_pages(extracted_text.pages, max_pages=max_pages, config=selection_config)
        )

    if resolved_mode in {"image", "hybrid"}:
        extracted_images = extract_images(pdf, max_pages=max_pages)
        selected_image_pages = (
            extracted_images.pages
            if max_pages is None
            else select_image_pages(extracted_images.pages, max_pages=max_pages, config=selection_config)
        )

    user_content = build_user_content_for_mode(
        resolved_mode=resolved_mode,
        text_pages=selected_text_pages,
        image_pages=selected_image_pages,
    )
    selected_page_numbers = _ordered_unique(
        [page.page_number for page in selected_text_pages] + [page.page_number for page in selected_image_pages]
    )
    return PdfInputPayload(
        requested_mode=input_mode,
        resolved_mode=resolved_mode,
        user_content=user_content,
        pages_used=len(selected_page_numbers),
        selected_page_numbers=selected_page_numbers,
        selected_text_pages=selected_text_pages,
        selected_image_pages=selected_image_pages,
    )


def coerce_input_mode(input_mode: PdfInputMode, *, prefer_text: bool = False) -> PdfInputMode:
    return "text" if prefer_text else input_mode


def _ordered_unique(values: list[int] | tuple[int, ...] | object) -> list[int]:
    seen: set[int] = set()
    ordered: list[int] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered
