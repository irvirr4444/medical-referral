from __future__ import annotations

import argparse
import os

from dotenv import load_dotenv

from gmail_alert.ids import ACTION_IDS
from gmail_alert.send_all import send_all_templates, send_one_template


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Send Gmail SLA catalog templates.")
    parser.add_argument(
        "--to",
        default=os.environ.get("GMAIL_ALERT_DEFAULT_TO", "").strip(),
        help="Recipient override (default: GMAIL_ALERT_DEFAULT_TO)",
    )
    parser.add_argument(
        "--only",
        choices=list(ACTION_IDS),
        help="Send a single template instead of the full catalog",
    )
    args = parser.parse_args()
    if not args.to:
        raise SystemExit("Pass --to or set GMAIL_ALERT_DEFAULT_TO")
    if args.only:
        sent = send_one_template(args.only, to=(args.to,))
        print(f"Sent {sent} to {args.to}")
        return
    sent = send_all_templates(to=(args.to,))
    print(f"Sent {len(sent)} of {len(ACTION_IDS)} templates to {args.to}")


if __name__ == "__main__":
    main()
