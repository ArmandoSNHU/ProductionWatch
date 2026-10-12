"""Sends steady synthetic traffic to the API so dashboards have data to show.

    python scripts/generate_traffic.py                # 60 requests, then exit
    python scripts/generate_traffic.py --loop --rps 2 # run until stopped
"""
import argparse
import itertools
import os
import sys
import time

import requests

PATHS = ["/accounts", "/accounts/1", "/accounts/2/transactions", "/accounts/3",
         "/accounts/4/transactions", "/health", "/accounts/5"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=os.getenv("API_URL", "http://localhost:8000"))
    parser.add_argument("--rps", type=float, default=2.0, help="requests per second")
    parser.add_argument("--count", type=int, default=60)
    parser.add_argument("--loop", action="store_true", help="run until interrupted")
    args = parser.parse_args()

    base = args.url.rstrip("/")
    interval = 1.0 / args.rps
    sent = 0
    counts: dict[str, int] = {}
    for path in itertools.cycle(PATHS):
        if not args.loop and sent >= args.count:
            break
        try:
            status = str(requests.get(base + path, timeout=10).status_code)
        except requests.RequestException as exc:
            status = type(exc).__name__
        counts[status] = counts.get(status, 0) + 1
        sent += 1
        if args.loop and sent % 60 == 0:
            print(f"sent={sent} status_counts={counts}", flush=True)
        time.sleep(interval)

    print(f"sent={sent} status_counts={counts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
