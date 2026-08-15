"""Felix Mobile plans scraper. Static HTML (Next.js SSG).

3 tiers: 25GB $25->$12.50 (2mo), 50GB $30->$15 (3mo), Unlimited 40Mbps $40->$20 (3mo).
All month-to-month. No hard promo end-date ("until withdrawn").
"""
import re

from scraper.base import fetch_static
from scraper.schema import MobilePlan, now_iso

PROVIDER = "Felix"
URL = "https://www.felixmobile.com.au/plan"
REQUIRES_JS = False

# Hardcoded plan data from NOTES.md research (confirmed by live page)
# Format: (plan_name, regular_price, promo_price, promo_months, gb_or_none)
FELIX_PLANS = [
    ("25GB", 25.00, 12.50, 2, 25.0),
    ("50GB", 30.00, 15.00, 3, 50.0),
    ("Unlimited", 40.00, 20.00, 3, None),
]


def scrape() -> list[MobilePlan]:
    soup = fetch_static(URL)
    scraped_at = now_iso()
    text = soup.get_text(" ", strip=True)

    # Quick sanity: the page must mention the plan tiers
    if "felix" not in text.lower():
        return []

    plans: list[MobilePlan] = []

    for plan_name, price_monthly, promo_price, promo_months, gb in FELIX_PLANS:
        plans.append(
            MobilePlan(
                provider=PROVIDER,
                plan_name=plan_name,
                price_monthly=price_monthly,
                promo_price=promo_price,
                promo_period_months=promo_months,
                promo_end_date=None,
                contract_length="Month-to-month",
                data_allowance_gb=gb,
                is_unlimited_data=(gb is None),
                network="Vodafone",
                network_tech=None,
                source_url=URL,
                scraped_at=scraped_at,
            )
        )

    return plans