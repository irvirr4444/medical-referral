from intake_extractor.pdf_inputs import build_user_content_for_mode, resolve_input_mode
from intake_extractor.pdf_payloads import PageImage, TextPage


def test_resolve_input_mode_prefers_text_when_auto_and_text_layer_exists() -> None:
    assert resolve_input_mode("auto", pdf_has_text_layer=True) == "text"


def test_resolve_input_mode_prefers_images_when_auto_and_no_text_layer() -> None:
    assert resolve_input_mode("auto", pdf_has_text_layer=False) == "image"


def test_hybrid_user_content_contains_text_and_images() -> None:
    text_pages = [TextPage(page_number=1, text="header block"), TextPage(page_number=2, text="service order")]
    image_pages = [
        PageImage(page_number=1, media_type="image/png", base64_data="abc"),
        PageImage(page_number=2, media_type="image/png", base64_data="def"),
    ]

    content = build_user_content_for_mode(
        resolved_mode="hybrid",
        text_pages=text_pages,
        image_pages=image_pages,
    )

    assert content[0]["type"] == "text"
    assert "INPUT TYPE: HYBRID" in content[0]["text"]
    assert "actual page numbers" in content[0]["text"]
    assert any(item["type"] == "image" for item in content)
    assert any(item["type"] == "text" and "--- PAGE 1 ---" in item["text"] for item in content[1:])


def test_image_user_content_keeps_only_images() -> None:
    image_pages = [PageImage(page_number=1, media_type="image/png", base64_data="abc")]

    content = build_user_content_for_mode(
        resolved_mode="image",
        text_pages=[],
        image_pages=image_pages,
    )

    assert content[0]["type"] == "text"
    assert "INPUT TYPE: IMAGES" in content[0]["text"]
    assert len(content) == 2
