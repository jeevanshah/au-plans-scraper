"""One-off: rebuild data/price_history.json from the git history of data/deals.json.

Usage: python backfill_price_history.py
"""
import json
import subprocess
from pathlib import Path

from scraper.price_history import build_price_events, merge_history

ROOT = Path(__file__).parent
OUT = ROOT / "data" / "price_history.json"


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def main() -> None:
    commits = git("log", "--reverse", "--format=%H %cs", "--", "data/deals.json").split("\n")
    commits = [c.split() for c in commits if c.strip()]
    previous, events = None, []
    for sha, day in commits:
        try:
            deals = json.loads(git("show", f"{sha}:data/deals.json"))
        except Exception:
            continue
        if not isinstance(deals, list):
            continue
        if previous is not None:
            events = build_price_events(deals, previous, day) + events
        previous = deals
    last_day = commits[-1][1] if commits else "1970-01-01"
    history = merge_history(events, [], last_day)
    OUT.write_text(json.dumps(history, indent=2), encoding="utf-8")
    print(f"{len(commits)} commits scanned, {len(history)} price events written to {OUT}")


if __name__ == "__main__":
    main()
