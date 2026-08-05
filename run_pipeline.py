"""Single operator entry point for the referral automation pipeline."""

from __future__ import annotations

import sys
from pathlib import Path


SRC_ROOT = Path(__file__).resolve().parent / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from referral_pipeline.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
