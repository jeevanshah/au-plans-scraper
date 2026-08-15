"""Dodo NBN plans scraper. Static HTML, no JS rendering needed."""
import re

from scraper.base import classify_tech_type, fetch_static, parse_absolute_end_date, parse_price
from scraper.schema import NbnPlan, now_iso

PROVIDER = "Dodo"
URL = "https://www.dodo.com/nbn"
REQUIRES_JS = False

CARD_RE = re.compile(
    r"MONTHS\s+([A-Z ]+?)\s+(NBN\d+/\d+)\s+\$([\d.]+)\s+\$(\d+)\s*\.\s*(\d+)\s*/mth"
)
SPEED_RE = re.compile(r"(\d+)\s*Mbps download,\s*(\d+)\s*Mbps upload")
PROMO_MONTHS_RE = re.compile(r"\$30 MTH OFF FOR (\d+) MONTHS")


def scrape() -> list[NbnPlan]:
    soup = fetch_static(URL)
    tiles = soup.find_all("div", class_="plan-tile")
    plans = []
    scraped_at = now_iso()

    for tile in tiles:
        text = tile.get_text(" ", strip=True)
        if "Available connection types FW" in text:
            continue  # Fixed Wireless variant, not a fixed-line NBN plan

        match = CARD_RE.search(text)
        if not match:
            continue

        plan_name, speed_tier, regular_price, promo_dollars, promo_cents = match.groups()
        speed_match = SPEED_RE.search(text)
        promo_months_match = PROMO_MONTHS_RE.search(text)

        plans.append(
            NbnPlan(
                provider=PROVIDER,
                plan_name=plan_name.strip().title(),
                price_monthly=parse_price(regular_price),
                promo_price=float(f"{promo_dollars}.{promo_cents}"),
                promo_period_months=int(promo_months_match.group(1)) if promo_months_match else None,
                promo_end_date=parse_absolute_end_date(text),
                contract_length="No lock-in contract",
                speed_tier=f"NBN {speed_tier.replace('NBN', '')}",
                typical_evening_speed_mbps=float(speed_match.group(1)) if speed_match else None,
                tech_type=classify_tech_type(text),
                source_url=URL,
                scraped_at=scraped_at,
            )
        )
    return plans
