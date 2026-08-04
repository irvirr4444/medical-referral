"""Shared Selenium/login helpers for DRK browser automation."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from selenium.webdriver import ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait
from seleniumwire import webdriver


LOGIN_PATH = "/Login/LoginView"
DASHBOARD_PATH = "/Dashboard"
PATIENT_DASHBOARD_PATH = "/PatientDashboard/Index/"


def safe_log(message: str) -> None:
    print(message, file=sys.stderr)


def require_env(key: str) -> str:
    value = os.getenv(key, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return value


def emr_root(emr_url: str) -> str:
    parsed = urlsplit(emr_url)
    if not parsed.scheme or not parsed.netloc:
        raise RuntimeError("EMR_URL must be an absolute URL")
    return f"{parsed.scheme}://{parsed.netloc}"


def login_url_for(emr_url: str) -> str:
    return f"{emr_root(emr_url)}{LOGIN_PATH}"


def make_driver(profile_dir: Path, *, window_size: str = "1400,1100") -> webdriver.Chrome:
    options = ChromeOptions()
    options.add_argument(f"--user-data-dir={profile_dir}")
    options.add_argument(f"--window-size={window_size}")
    options.add_argument("--no-first-run")
    options.add_argument("--disable-sync")
    return webdriver.Chrome(
        options=options,
        seleniumwire_options={"request_storage": "memory", "disable_encoding": False},
    )


def login(driver: webdriver.Chrome, login_url: str, username: str, password: str) -> None:
    wait = WebDriverWait(driver, 30)
    driver.get(login_url)
    user = wait.until(
        ec.presence_of_element_located(
            (
                By.XPATH,
                "//input[@placeholder='User Name' or @name='User Name' or @id='UserName' or @name='UserName']",
            )
        )
    )
    pwd = wait.until(ec.presence_of_element_located((By.XPATH, "//input[@type='password']")))
    user.clear()
    user.send_keys(username)
    pwd.clear()
    pwd.send_keys(password)
    login_btn = wait.until(ec.element_to_be_clickable((By.XPATH, "//button[normalize-space()='Login']")))
    login_btn.click()
    wait.until(lambda d: DASHBOARD_PATH.lower() in d.current_url.lower())


def extract_patient_id_from_url(url: str) -> str | None:
    parsed = urlsplit(url)
    from urllib.parse import parse_qs

    query = parse_qs(parsed.query)
    values = query.get("patientId") or query.get("patientid")
    if values and values[0].strip():
        return values[0].strip()
    return None


def patient_dashboard_url(emr_url: str, patient_id: str) -> str:
    return f"{emr_root(emr_url)}{PATIENT_DASHBOARD_PATH}?patientId={patient_id}"


def clear_network_requests(driver: Any) -> None:
    try:
        driver.requests.clear()
    except Exception:
        pass
