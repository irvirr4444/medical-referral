"""Convenience entry point for a Master Sheet status query."""

from __future__ import annotations

import sys

from read_master_sheet import main


if __name__ == "__main__":
    raise SystemExit(main(["status", *sys.argv[1:]]))
