from __future__ import annotations

from pathlib import Path

from drk_emr.common import browser


def test_make_driver_uses_an_absolute_profile_path(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_chrome(*, options, seleniumwire_options):
        captured["arguments"] = options.arguments
        captured["seleniumwire_options"] = seleniumwire_options
        return object()

    monkeypatch.setattr(browser.webdriver, "Chrome", fake_chrome)

    result = browser.make_driver(Path("tmp/relative-drk-profile"))

    profile_argument = next(
        argument
        for argument in captured["arguments"]
        if argument.startswith("--user-data-dir=")
    )
    assert Path(profile_argument.split("=", 1)[1]).is_absolute()
    assert captured["seleniumwire_options"] == {
        "request_storage": "memory",
        "disable_encoding": False,
    }
    assert result is not None
