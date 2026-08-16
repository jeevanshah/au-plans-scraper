"""iiNet NBN plans scraper. Client-rendered plan cards -- requires Playwright.

Plan tiers and prices render client-side (same pattern as Superloop).
Promo copy and tech-type text is in the raw HTML.

Promos: "$20/mth off for 6 months" (NBN25/50), "$25/mth off for 6 months"
(NBN100/500), "$30/mth off for 6 months" (Superfast/Ultrafast).
"""
import re

from scraper.base import classify_tech_type, fetch_js, parse_price, normalize_nbn_speed_tier
from scraper.schema import NbnPlan, now_iso

PROVIDER = "iiNet"
URL = "https://www.iinet.net.au/internet-product/broadband/nbn/plans/fibre"
REQUIRES_JS = True

SPEED_RE = re.compile(r"(?:NBN|nbn)\s*(\d+)(?:/(\d+))?", re.I)
PRICE_RE = re.compile(r"\$(\d+\.?\d*)")
PROMO_OFF_RE = re.compile(r"\$(\d+)/mth\s+off\s+for\s+(\d+)\s+months?", re.I)


def scrape() -> list[NbnPlan]:
    soup = fetch_js(URL, settle_ms=5000)
    scraped_at = now_iso()
    text = soup.get_text(" ", strip=True)
    plans: list[NbnPlan] = []
    seen_tiers: set[str] = set()

    # Find promo text for discount info
    promo_match = PROMO_OFF_RE.search(text)

    # Parse plan cards. iiNet renders card-like divs with speed+price data.
    for tag in soup.find_all(["div", "article", "section"]):
        txt = tag.get_text(" ", strip=True)
        if len(txt) < 20 or len(txt) > 500:
            continue
        speed_m = SPEED_RE.search(txt)
        if not speed_m:
            continue

        down = speed_m.group(1)
        up = speed_m.group(2)
        speed_tier, _, _ = normalize_nbn_speed_tier(down, up)

        if speed_tier in seen_tiers:
            continue
        seen_tiers.add(speed_tier)

        prices = PRICE_RE.findall(txt)
        if not prices:
            continue

        regular_price = float(prices[-1])
        promo_price: float | None = None
        promo_months: int | None = None

        if promo_match:
            promo_months = int(promo_match.group(2))
            discount = float(promo_match.group(1))
            promo_price = regular_price - discount
            if promo_price <= 0:
                promo_price = None
                promo_months = None

        # Plan name / title
        name_el = tag.find(["h2", "h3", "h4", "strong"])
        if name_el:
            plan_name = name_el.get_text(strip=True)
        else:
            plan_name = speed_tier

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