"""CLI quality gate for committed synthetic vocabulary banks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .vocab_rules import DATA_PATH, load_vocabulary_data, validate_vocabulary_payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate synthetic vocabulary_data.json quality gates.")
    parser.add_argument("--path", type=Path, default=DATA_PATH)
    args = parser.parse_args(argv)
    payload = load_vocabulary_data(args.path)
    failures = validate_vocabulary_payload(payload)
    summary = {
        "path": str(args.path.resolve()),
        "ok": not failures,
        "failure_count": len(failures),
        "failures": failures[:50],
        "counts": {
            key: len(payload.get(key) or [])
            for key in (
                "first_names",
                "last_names",
                "facilities",
                "insurers",
                "medications",
                "note_fragments",
                "diagnoses",
                "service_instructions",
                "service_frequencies",
                "street_names",
                "cities",
            )
        },
    }
    print(json.dumps(summary, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
