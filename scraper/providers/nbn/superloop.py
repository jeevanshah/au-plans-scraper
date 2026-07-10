"""Superloop NBN plans scraper.

Superloop's plan cards are a Gatsby+React page that renders empty on a plain
static fetch and even right after Playwright's "load" event -- the cards
hydrate a moment later, so fetch_js needs an explicit settle_ms wait.
"""
import re

from scraper.base import fetch_js, parse_price
from scraper.schema import NbnPlan, now_iso

PROVIDER = "Superloop"
URL = "https://www.superloop.com/internet/nbn/"
REQUIRES_JS = True

SPEED_RE = re.compile(r"Download\s*(\d+)\s*Mbps\s*Upload\s*(\d+)\s*Mbps")
PRICE_RE = re.compile(r"\$(\d+)\s*\$(\d+)\s*/mth")
PROMO_MONTHS_RE = re.compile(r"For first (\d+) months? then")
TYPICAL_SPEED_RE = re.compile(r"Typical evening speed\s*(\d+)/[\d.]+\s*Mbps")


def scrape() -> list[NbnPlan]:
    soup = fetch_js(URL, settle_ms=4000)
    cards = soup.find_all("div", class_=lambda c: c and "shadow-md" in c and "bg-white" in c)
    plans = []
    scraped_at = now_iso()

    for card in cards:
        text = card.get_text(" ", strip=True)
        name_el = card.find("h3")
        speed_match = SPEED_RE.search(text)
        price_match = PRICE_RE.search(text)
        if not (name_el and speed_match and price_match):
            continue

        regular_price, promo_price = price_match.groups()
        promo_months_match = PROMO_MONTHS_RE.search(text)
        typical_match = TYPICAL_SPEED_RE.search(text)
        down_mbps, up_mbps = speed_match.groups()

        plans.append(
            NbnPlan(
                provider=PROVIDER,
                plan_name=name_el.get_text(strip=True),
                price_monthly=parse_price(regular_price),
                promo_price=parse_price(promo_price),
                promo_period_months=int(promo_months_match.group(1)) if promo_months_match else None,
                contract_length="No lock-in contract",
                speed_tier=f"NBN {down_mbps}/{up_mbps}",
                typical_evening_speed_mbps=float(typical_match.group(1)) if typical_match else None,
                source_url=URL,
                scraped_at=scraped_at,
            )
        )
    return plans
