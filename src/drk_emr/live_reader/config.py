"""Environment-backed configuration for continuous DRK reads."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from drk_emr.common.browser import require_env


@dataclass(frozen=True)
class DrkLiveReaderConfig:
    emr_url: str
    username: str
    password: str
    profile_dir: Path
    headless: bool = True
    page_timeout_seconds: float = 30.0
    network_idle_seconds: float = 2.5

    @classmethod
    def from_environment(cls, *, profile_dir: str | Path) -> "DrkLiveReaderConfig":
        load_dotenv()
        return cls(
            emr_url=require_env("EMR_URL"),
            username=require_env("EMR_USERNAME"),
            password=require_env("EMR_PASSWORD"),
            profile_dir=Path(profile_dir),
            headless=_env_flag("DRK_LIVE_HEADLESS", default=True),
            page_timeout_seconds=float(os.getenv("DRK_LIVE_PAGE_TIMEOUT_SECONDS", "30")),
            network_idle_seconds=float(os.getenv("DRK_LIVE_NETWORK_IDLE_SECONDS", "2.5")),
        )


def _env_flag(name: str, *, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().casefold() in {"1", "true", "yes", "on"}
