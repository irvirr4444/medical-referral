from dataclasses import dataclass

from intake_extractor.selection import PageSelectionConfig, select_image_pages, select_text_pages


@dataclass(frozen=True)
class FakeTextPage:
    page_number: int
    text: str


@dataclass(frozen=True)
class FakeImagePage:
    page_number: int


def test_select_text_pages_prefers_referral_content() -> None:
    pages = [
        FakeTextPage(1, "fax cover sheet"),
        FakeTextPage(2, "general hospital narrative"),
        FakeTextPage(3, "referral to home health outpatient order provider diagnosis wound care"),
        FakeTextPage(4, "insurance member id subscriber group"),
    ]

    selected = select_text_pages(pages, max_pages=2, config=PageSelectionConfig(max_text_pages=2))

    assert [page.page_number for page in selected] == [1, 3]


def test_select_image_pages_keeps_front_window_and_last_page_for_long_packets() -> None:
    pages = [FakeImagePage(page_number=i) for i in range(1, 11)]

    selected = select_image_pages(pages, max_pages=6, config=PageSelectionConfig(max_vision_pages=6))

    assert [page.page_number for page in selected] == [1, 2, 3, 4, 5, 10]
