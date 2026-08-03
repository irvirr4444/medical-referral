"""Generate a self-contained, non-PHI set of referral-email test fixtures."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from synthetic_referrals import write_synthetic_fixture_set


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate synthetic referral PDFs, email fixtures, and local Monday snapshots.")
    parser.add_argument("--output-dir", type=Path, default=Path("tmp") / "synthetic-referrals")
    args = parser.parse_args(argv)
    print(json.dumps(write_synthetic_fixture_set(args.output_dir), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
