"""TPG NBN plans scraper. Static HTML.

TPG is Australia's 2nd-largest NBN retailer. Plans appear in plan-container
divs with speed tier labels and monthly pricing.
"""
import re

from scraper.base import classify_tech_type, fetch_static, parse_price
from scraper.schema import NbnPlan, now_iso

PROVIDER = "TPG"
URL = "https://www.tpg.com.au/nbn"
REQUIRES_JS = False

SPEED_RE = re.compile(r"(?:NBN|nbn)\s*(\d+)(?:/(\d+))?", re.I)
PRICE_RE = re.compile(r"\$\s*(\d+\.?\d*)", re.I)
PROMO_MONTHS_RE = re.compile(r"(?:off\s+for|first)\s+(\d+)\s+months?", re.I)


def scrape():
    soup = fetch_static(URL)
    scraped_at = now_iso()
    text = soup.get_text(" ", strip=True)

    plans = []
    seen_tiers = set()

    # TPG plan cards are in plan-container divs
    for card in soup.find_all(class_=lambda c: c and "plan-container" in " ".join(c)):
        txt = card.get_text(" ", strip=True)
        if len(txt) < 30:
            continue

        speed_m = SPEED_RE.search(txt)
        if not speed_m:
            continue

        down = speed_m.group(1)
        up = speed_m.group(2) if speed_m.group(2) else down
        speed_tier = "NBN {}/{}".format(down, up)

        if speed_tier in seen_tiers:
            continue
        seen_tiers.add(speed_tier)

        prices = PRICE_RE.findall(txt)
        if not prices:
            continue

        vals = sorted(set(float(p) for p in prices if float(p) > 1))
        promo_months_m = PROMO_MONTHS_RE.search(txt)

        regular_price = None
        promo_price = None
        promo_months = None

        if len(vals) >= 2:
            promo_price = vals[0]
            regular_price = vals[1]
        elif vals:
            regular_price = vals[0]

        if regular_price is None or regular_price <= 1:
            continue

        if promo_months_m:
            promo_months = int(promo_months_m.group(1))

        name_el = card.find(["h2", "h3", "h4", "strong"])
        plan_name = name_el.get_text(strip=True) if name_el else speed_tier

        plans.append(
            NbnPlan(
                provider=PROVIDER,
                plan_name=plan_name,
                price_monthly=regular_price,
                promo_price=promo_price,
                promo_period_months=promo_months,
                contract_length="No lock-in contract",
                speed_tier=speed_tier,
                tech_type=classify_tech_type(txt),
                source_url=URL,
                scraped_at=scraped_at,
            )
        )

    return plans