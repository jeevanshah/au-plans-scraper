"""Tangerine Telecom NBN plans scraper. Static HTML, no JS rendering needed."""
import re

from scraper.base import fetch_static, parse_price
from scraper.schema import NbnPlan, now_iso

PROVIDER = "Tangerine"
URL = "https://www.tangerinetelecom.com.au/nbn/nbn-broadband"
REQUIRES_JS = False

SPEED_RE = re.compile(r"([\d.]+)\s*Mbps Download\s*/\s*([\d.]+)\s*Mbps Upload")
ONGOING_RE = re.compile(r"then \$([\d.]+) ongoing")


def scrape() -> list[NbnPlan]:
    soup = fetch_static(URL)
    cols = soup.find_all("div", class_=lambda c: c and "product-speeds" in c)
    plans = []
    scraped_at = now_iso()

    for col in cols:
        name_el = col.find("h3")
        price_el = col.find("span", class_=lambda c: c and "heading" in c)
        footer_el = col.find("p", class_=lambda c: c and "plan_footer" in c)
        speed_el = col.find("div", class_=lambda c: c and "plan-speed" in c)
        if not (name_el and price_el and footer_el and speed_el):
            continue

        speed_match = SPEED_RE.search(speed_el.get_text(" ", strip=True))
        ongoing_match = ONGOING_RE.search(footer_el.get_text(" ", strip=True))
        if not (speed_match and ongoing_match):
            continue

        down, up = speed_match.groups()
        promo_period_match = re.search(r"For (\d+) months", footer_el.get_text(" ", strip=True))

        plans.append(
            NbnPlan(
                provider=PROVIDER,
                plan_name=name_el.get_text(strip=True),
                price_monthly=parse_price(ongoing_match.group(1)),
                promo_price=parse_price(price_el.get_text(strip=True)),
                promo_period_months=int(promo_period_match.group(1)) if promo_period_match else None,
                contract_length="No lock-in contract",
                speed_tier=f"NBN {int(float(down))}/{up}",
                typical_evening_speed_mbps=float(down),
                source_url=URL,
                scraped_at=scraped_at,
            )
        )
    return plans
