from __future__ import annotations

import argparse
import json
from typing import Any

from monday_api import DEFAULT_API_VERSION, DEFAULT_TIMEOUT_S, monday_graphql


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Minimal Monday.com GraphQL client (reads MONDAY_DOT_COM_API_KEY).",
    )
    p.add_argument(
        "--query",
        help='GraphQL query/mutation string (default: "{ me { id name email } }").',
    )
    p.add_argument(
        "--variables-json",
        help='Variables JSON object string, e.g. \'{"boardId": 123}\'.',
    )
    p.add_argument("--api-version", default=DEFAULT_API_VERSION)
    p.add_argument("--timeout-s", type=int, default=DEFAULT_TIMEOUT_S)
    p.add_argument("--pretty", action="store_true")
    p.add_argument(
        "--data-only",
        action="store_true",
        help="Print only the 'data' payload (when present).",
    )
    args = p.parse_args(argv)

    query = args.query or "{ me { id name email } }"
    variables = json.loads(args.variables_json) if args.variables_json else None

    resp = monday_graphql(
        query,
        variables=variables,
        api_version=args.api_version,
        timeout_s=args.timeout_s,
    )
    out: Any = resp.get("data") if (args.data_only and isinstance(resp, dict)) else resp

    print(json.dumps(out, indent=2 if args.pretty else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

