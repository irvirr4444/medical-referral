"""Convenience entry point for the Master Sheet intake queue."""

from __future__ import annotations

import sys

from read_master_sheet import main


if __name__ == "__main__":
    raise SystemExit(main(["intake", *sys.argv[1:]]))
