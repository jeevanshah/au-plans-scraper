"""Telstra NBN plans scraper. Static HTML, no JS rendering needed.

Telstra's plan cards page is built with Adobe Experience Manager and ships
several connection-type/AB-test variants of each tier in the same HTML
(hidden/shown via client-side JS). We deterministically pick the first
variant per tier that contains both "Internet Only" and "Typical speeds" --
this gives internally-consistent day-to-day tracking, but the exact price
picked may correspond to a specific connection type (e.g. FTTN) rather than
the cheapest available variant for a given address. Revisit if Telstra
restructures this page.
"""
import re

from scraper.base import fetch_static, parse_price
from scraper.schema import NbnPlan, now_iso

PROVIDER = "Telstra"
URL = "https://www.telstra.com.au/internet/nbn"
REQUIRES_JS = False

TIER_IDS = {
    "core-plan": "Basic",
    "essential-plan": "Essential",
    "premium-plan": "Premium",
    "awesome-plan": "Ultimate",
    "ultrafast-plan": "Ultrafast",
}

NBN_TIER_RE = re.compile(r"nbn.?(\d+)", re.IGNORECASE)
SPEED_RE = re.compile(r"(\d+)\s*Mbps Download\s*(\d+)\s*Mbps Upload")
PROMO_RE = re.compile(r"\$([\d.]+)\s*/\s*mth\s+For (\d+) months?, then \$([\d.]+)/mth")
FLAT_PRICE_RE = re.compile(r"\$([\d.]+)\s*/\s*mth\s+Plan price may change")


def _pick_variant(containers, plan_id):
    for c in containers:
        if c.get("id") != plan_id:
            continue
        text = c.get_text(" ", strip=True)
        if "Internet Only" in text and "Typical speeds" in text:
            return text
    return None


def scrape() -> list[NbnPlan]:
    soup = fetch_static(URL)
    containers = soup.find_all("div", class_=lambda c: c and "tcom-fixed-plan-card-container" in c)
    plans = []
    scraped_at = now_iso()

    for plan_id, plan_name in TIER_IDS.items():
        text = _pick_variant(containers, plan_id)
        if not text:
            continue

        tier_match = NBN_TIER_RE.search(text)
        speed_match = SPEED_RE.search(text)
        promo_match = PROMO_RE.search(text)

        if promo_match:
            promo_price = parse_price(promo_match.group(1))
            promo_period_months = int(promo_match.group(2))
            price_monthly = parse_price(promo_match.group(3))
        else:
            flat_match = FLAT_PRICE_RE.search(text)
            if not flat_match:
                continue
            price_monthly = parse_price(flat_match.group(1))
            promo_price = None
            promo_period_months = None

        plans.append(
            NbnPlan(
                provider=PROVIDER,
                plan_name=plan_name,
                price_monthly=price_monthly,
                promo_price=promo_price,
                promo_period_months=promo_period_months,
                contract_length="No lock-in contract (month-to-month)",
                speed_tier=f"NBN {tier_match.group(1)}" if tier_match else "NBN (tier unknown)",
                typical_evening_speed_mbps=float(speed_match.group(1)) if speed_match else None,
                source_url=URL,
                scraped_at=scraped_at,
            )
        )
    return plans
