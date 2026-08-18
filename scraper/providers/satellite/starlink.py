"""Starlink Australia residential plans scraper. JS-rendered (React/MUI single-page
app) -- prices are baked into the initial page render, so no address entry is needed."""
import re

from scraper.base import fetch_js
from scraper.schema import SatellitePlan, now_iso

PROVIDER = "Starlink"
URL = "https://www.starlink.com/au/residential"
REQUIRES_JS = True

PRICE_RE = re.compile(r"SERVICE STARTING AT A\$(?P<price>[\d.]+)\s*/mo")


def scrape() -> list[SatellitePlan]:
    soup = fetch_js(URL, wait_until="load", settle_ms=3000)
    plans = []
    scraped_at = now_iso()

    for h4 in soup.find_all("h4", class_=lambda c: c and "MuiTypography-h4" in c):
        name_text = h4.get_text(strip=True)
        if not name_text.startswith("Residential"):
            continue

        card = h4.parent
        for _ in range(8):
            if card is None:
                break
            text = card.get_text(" ", strip=True)
            if "SERVICE STARTING AT" in text and len(text) < 600:
                break
            card = card.parent
        if card is None:
            continue

        match = PRICE_RE.search(text)
        if not match:
            continue

        plan_name = name_text
        price_monthly = float(match.group("price"))

        # The page states "No upfront hardware cost in select areas" without a numeric
        # figure, and the actual dish/kit cost is address-dependent -- don't fabricate one.
        upfront_hardware_cost = None

        plans.append(
            SatellitePlan(
                provider=PROVIDER,
                plan_name=plan_name,
                price_monthly=price_monthly,
                promo_price=None,
                promo_period_months=None,
                upfront_hardware_cost=upfront_hardware_cost,
                data_allowance_gb=None,
                is_unlimited_data=True,
                network="Starlink",
                contract_length="No lock-in contract",
                source_url=URL,
                scraped_at=scraped_at,
            )
        )
    return plans
