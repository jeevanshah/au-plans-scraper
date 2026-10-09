"""Price-change history for the public site (provider pages, price-rise tracker).

Each event records one plan whose promo price, ongoing price or promo length
changed between two scraper runs. Plans are keyed by (provider, serviceType,
tier) -- the same key as the changelog -- because `id` rotates monthly.

Changes outside PLAUSIBLE_RATIO are skipped: they are far more likely to be
parser drift than a real price move, and this data is shown publicly.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

PRICE_FIELDS = ("promoPrice", "regularPrice", "promoMonths")
PLAUSIBLE_RATIO = (0.5, 2.0)
MAX_AGE_DAYS = 400


def _key(d: dict) -> tuple:
    # tier alone collides for mobile (e.g. a 28-day and a 365-day 160GB plan),
    # so the billing cycle and title are part of the identity too.
    return (
        d.get("provider", ""), d.get("serviceType", ""), d.get("tier", ""),
        d.get("billingCycleDays"), (d.get("title") or "").strip().lower(),
    )


def _plausible(old, new) -> bool:
    try:
        old, new = float(old), float(new)
    except (TypeError, ValueError):
        return False
    if old <= 0 or new <= 0:
        return False
    return PLAUSIBLE_RATIO[0] <= new / old <= PLAUSIBLE_RATIO[1]


def build_price_events(all_deals: list[dict], previous_deals: list[dict], today: str) -> list[dict]:
    from collections import Counter

    cur_counts = Counter(_key(d) for d in all_deals)
    prev_counts = Counter(_key(d) for d in previous_deals or [])
    prev_index = {_key(d): d for d in previous_deals or []}
    events = []
    for deal in all_deals:
        k = _key(deal)
        # Two plans sharing one identity can't be matched reliably; skip
        # rather than publish a phantom price change.
        if cur_counts[k] > 1 or prev_counts[k] > 1:
            continue
        prev = prev_index.get(k)
        if prev is None:
            continue
        changes = {}
        for f in ("promoPrice", "regularPrice"):
            if deal.get(f) != prev.get(f) and _plausible(prev.get(f), deal.get(f)):
                changes[f] = [prev.get(f), deal.get(f)]
        if deal.get("promoMonths") != prev.get("promoMonths") and changes:
            changes["promoMonths"] = [prev.get("promoMonths"), deal.get("promoMonths")]
        if changes:
            events.append({
                "date": today,
                "provider": deal.get("provider", ""),
                "serviceType": deal.get("serviceType", ""),
                "tier": deal.get("tier", ""),
                "title": deal.get("title", ""),
                "billingCycleDays": deal.get("billingCycleDays"),
                "changes": changes,
            })
    return events


def collapse_same_day(events: list[dict]) -> list[dict]:
    """Merge several runs on one day into a single net change per plan, and
    drop changes that reverted within the day (scraper flip-flops)."""
    order: list[tuple] = []
    merged: dict[tuple, dict] = {}
    # oldest first so "from" comes from the earliest and "to" from the latest
    for e in sorted(events, key=lambda e: e["date"]):
        k = (e["date"], e.get("provider"), e.get("serviceType"), e.get("tier"),
             e.get("billingCycleDays"), (e.get("title") or "").strip().lower())
        if k not in merged:
            merged[k] = {**e, "changes": {f: list(v) for f, v in e["changes"].items()}}
            order.append(k)
            continue
        cur = merged[k]
        cur["title"] = e.get("title") or cur.get("title")
        for f, (old, new) in e["changes"].items():
            if f in cur["changes"]:
                cur["changes"][f][1] = new
            else:
                cur["changes"][f] = [old, new]
    out = []
    for k in order:
        e = merged[k]
        e["changes"] = {f: v for f, v in e["changes"].items() if v[0] != v[1]}
        if any(f in e["changes"] for f in ("promoPrice", "regularPrice")):
            out.append(e)
    return out


def merge_history(new_events: list[dict], existing: list[dict], today: str) -> list[dict]:
    cutoff = (date.fromisoformat(today) - timedelta(days=MAX_AGE_DAYS)).isoformat()
    combined = [e for e in (new_events + (existing or [])) if e.get("date", "") >= cutoff]
    combined = collapse_same_day(combined)
    combined.sort(key=lambda e: e["date"], reverse=True)
    return combined


def write_history(path: Path, new_events: list[dict], today: str) -> int:
    existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    merged = merge_history(new_events, existing, today)
    path.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    return len(merged)
