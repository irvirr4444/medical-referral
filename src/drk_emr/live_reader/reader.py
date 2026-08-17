"""Batch DRK patient reader using one authenticated Selenium session."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

from selenium.webdriver import ChromeOptions
from selenium.webdriver.support.ui import WebDriverWait
from seleniumwire import webdriver

from drk_emr.common.browser import (
    DASHBOARD_PATH,
    LOGIN_PATH,
    clear_network_requests,
    emr_root,
    login,
    login_url_for,
    patient_dashboard_url,
)
from drk_emr.live_reader.capture import (
    DrkCaptureError,
    attach_diagnosis_dom,
    capture_dashboard_cards,
    fill_missing_cards_via_fetch,
    scrape_diagnosis_card,
    wait_for_network_idle,
)
from drk_emr.live_reader.config import DrkLiveReaderConfig


PATIENT_ID_RE = re.compile(r"^[0-9]+$")


class DrkLiveReaderError(RuntimeError):
    pass


@dataclass(frozen=True)
class DrkPatientCapture:
    patient_id: str
    observed_at: datetime
    cards: dict[str, dict[str, Any]]


DriverFactory = Callable[[DrkLiveReaderConfig], Any]
LoginFunction = Callable[[Any, str, str, str], None]


class DrkPatientReader:
    """Open one browser per batch and navigate directly by verified patient ID."""

    def __init__(
        self,
        config: DrkLiveReaderConfig,
        *,
        driver_factory: DriverFactory | None = None,
        login_function: LoginFunction = login,
    ) -> None:
        self.config = config
        self.driver_factory = driver_factory or _make_driver
        self.login_function = login_function
        self.driver: Any | None = None

    def __enter__(self) -> "DrkPatientReader":
        self.open()
        return self

    def __exit__(self, _type: object, _value: object, _traceback: object) -> None:
        self.close()

    def open(self) -> None:
        if self.driver is not None:
            return
        self.config.profile_dir.mkdir(parents=True, exist_ok=True)
        self.driver = self.driver_factory(self.config)
        self._authenticate()

    def close(self) -> None:
        if self.driver is None:
            return
        try:
            self.driver.quit()
        finally:
            self.driver = None

    def read_patient(self, patient_id: str) -> DrkPatientCapture:
        normalized_id = str(patient_id).strip()
        if not PATIENT_ID_RE.fullmatch(normalized_id):
            raise ValueError("DRK live reader requires a numeric patient ID")
        self.open()
        assert self.driver is not None
        for attempt in range(2):
            clear_network_requests(self.driver)
            self.driver.get(patient_dashboard_url(self.config.emr_url, normalized_id))
            if _is_login_page(self.driver):
                if attempt == 0:
                    self._authenticate()
                    continue
                raise DrkLiveReaderError("DRK session returned to login during patient read")
            WebDriverWait(self.driver, self.config.page_timeout_seconds).until(
                lambda current: normalized_id in current.current_url
            )
            wait_for_network_idle(
                self.driver,
                idle_seconds=self.config.network_idle_seconds,
                timeout_seconds=self.config.page_timeout_seconds,
            )
            cards = capture_dashboard_cards(
                self.driver,
                allowed_host=urlsplit(emr_root(self.config.emr_url)).netloc,
                patient_id=normalized_id,
                require_demographics=False,
            )
            cards = fill_missing_cards_via_fetch(self.driver, cards, normalized_id)
            if not cards.get("patient_information", {}).get("records"):
                raise DrkCaptureError("DRK patient demographics response was not captured")
            cards = attach_diagnosis_dom(cards, scrape_diagnosis_card(self.driver))
            return DrkPatientCapture(
                patient_id=normalized_id,
                observed_at=datetime.now(timezone.utc),
                cards=cards,
            )
        raise DrkLiveReaderError("DRK patient read failed after reauthentication")

    def _authenticate(self) -> None:
        assert self.driver is not None
        self.driver.get(f"{emr_root(self.config.emr_url)}{DASHBOARD_PATH}")
        if (
            DASHBOARD_PATH.casefold() in self.driver.current_url.casefold()
            and not _is_login_page(self.driver)
        ):
            return
        self.login_function(
            self.driver,
            login_url_for(self.config.emr_url),
            self.config.username,
            self.config.password,
        )
        if DASHBOARD_PATH.casefold() not in self.driver.current_url.casefold():
            raise DrkLiveReaderError("DRK authentication did not reach the dashboard")


def _is_login_page(driver: Any) -> bool:
    return LOGIN_PATH.casefold() in str(driver.current_url).casefold()


def _make_driver(config: DrkLiveReaderConfig) -> webdriver.Chrome:
    options = ChromeOptions()
    options.add_argument(f"--user-data-dir={Path(config.profile_dir).resolve()}")
    options.add_argument("--window-size=1600,1200")
    options.add_argument("--no-first-run")
    options.add_argument("--disable-sync")
    if config.headless:
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(
        options=options,
        seleniumwire_options={"request_storage": "memory", "disable_encoding": False},
    )
