"""Telstra SIM-only mobile plans scraper. Static HTML, no JS rendering needed."""
import re

from scraper.base import fetch_static
from scraper.schema import MobilePlan, now_iso

PROVIDER = "Telstra"
URL = "https://www.telstra.com.au/mobile-phones/sim-only-plans"
REQUIRES_JS = False

CARD_RE = re.compile(r"^(\w+)\s+(\d+)GB for \$(\d+)\s*/mth")


def scrape() -> list[MobilePlan]:
    soup = fetch_static(URL)
    cards = soup.find_all("li", class_=lambda c: c and "plan-card--subscription" in c)
    plans = []
    scraped_at = now_iso()

    for card in cards:
        text = card.get_text(" ", strip=True)
        match = CARD_RE.search(text)
        if not match:
            continue

        plan_name, data_gb, price = match.groups()

        plans.append(
            MobilePlan(
                provider=PROVIDER,
                plan_name=plan_name,
                price_monthly=float(price),
                promo_price=None,
                promo_period_months=None,
                contract_length="Month-to-month",
                data_allowance_gb=float(data_gb),
                is_unlimited_data=False,
                network="Telstra",
                source_url=URL,
                scraped_at=scraped_at,
            )
        )
    return plans
