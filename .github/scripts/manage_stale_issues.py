"""Upsert/close a single GitHub Issue per provider based on data/meta.json.

Run in CI after run.py. Opens (or updates) one "stale: <provider>" issue when
a provider hits the consecutive-failure threshold, and closes it once the
provider recovers. Never opens duplicate issues for the same provider.
"""
import json
import subprocess
import sys
from pathlib import Path

THRESHOLD = 3
META_PATH = Path(__file__).parent.parent.parent / "data" / "meta.json"


def gh(*args: str) -> str:
    result = subprocess.run(["gh", *args], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"gh {' '.join(args)} failed: {result.stderr}", file=sys.stderr)
    return result.stdout.strip()


def find_open_issue(title: str) -> str | None:
    output = gh(
        "issue", "list", "--state", "open", "--search", f'"{title}" in:title',
        "--json", "number,title", "--jq", f'.[] | select(.title == "{title}") | .number',
    )
    return output.splitlines()[0] if output else None


def main() -> None:
    if not META_PATH.exists():
        print("No meta.json found, nothing to do")
        return

    meta = json.loads(META_PATH.read_text(encoding="utf-8"))

    for provider, status in meta.items():
        title = f"stale: {provider}"
        failures = status.get("consecutive_failures", 0)
        existing_issue = find_open_issue(title)

        if failures >= THRESHOLD and not existing_issue:
            body = (
                f"`{provider}`'s scraper has failed {failures} consecutive runs.\n\n"
                f"Last known success: {status.get('last_success') or 'never'}\n\n"
                "The last-known-good plan data is still being served, but it is "
                "now stale. Check the provider's page for a layout/markup change."
            )
            gh("issue", "create", "--title", title, "--body", body, "--label", "scraper-stale")
            print(f"Opened issue for {provider} ({failures} consecutive failures)")
        elif failures < THRESHOLD and existing_issue:
            gh(
                "issue", "close", existing_issue,
                "--comment", f"`{provider}` recovered (last success: {status.get('last_success')}).",
            )
            print(f"Closed stale issue for {provider} (recovered)")


if __name__ == "__main__":
    main()
