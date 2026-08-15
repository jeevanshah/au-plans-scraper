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
LABEL = "scraper-stale"

_had_failure = False


def gh(*args: str) -> str:
    result = subprocess.run(["gh", *args], capture_output=True, text=True)
    if result.returncode != 0:
        global _had_failure
        _had_failure = True
        print(f"gh {' '.join(args)} failed: {result.stderr}", file=sys.stderr)
    return result.stdout.strip()


def ensure_label_exists() -> None:
    # gh issue create --label X fails outright if the label doesn't already
    # exist on the repo -- this silently broke every issue-creation attempt
    # for weeks (the repo never had a "scraper-stale" label) because gh()
    # only logs failures, it doesn't raise. --force makes this idempotent:
    # creates the label if missing, updates it in place if already there.
    gh(
        "label", "create", LABEL, "--force",
        "--color", "d73a4a",
        "--description", "Opened automatically when a provider scraper hits 3+ consecutive failures",
    )


def find_open_issue(title: str) -> str | None:
    output = gh(
        "issue", "list", "--state", "open", "--search", f'"{title}" in:title',
        "--json", "number,title", "--jq", f'.[] | select(.title == "{title}") | .number',
    )
    return output.splitlines()[0] if output else None


def main() -> int:
    if not META_PATH.exists():
        print("No meta.json found, nothing to do")
        return 0

    ensure_label_exists()

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
            gh("issue", "create", "--title", title, "--body", body, "--label", LABEL)
            print(f"Opened issue for {provider} ({failures} consecutive failures)")
        elif failures < THRESHOLD and existing_issue:
            gh(
                "issue", "close", existing_issue,
                "--comment", f"`{provider}` recovered (last success: {status.get('last_success')}).",
            )
            print(f"Closed stale issue for {provider} (recovered)")

    # Propagate real gh failures as a non-zero exit -- this step has no
    # continue-on-error in the workflow, so this is what actually surfaces
    # a broken automation in the Actions UI instead of silently no-op'ing,
    # which is exactly how the missing-label bug went unnoticed for weeks.
    return 1 if _had_failure else 0


if __name__ == "__main__":
    sys.exit(main())
