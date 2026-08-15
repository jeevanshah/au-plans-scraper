"""Vodafone SIM-only mobile plans scraper. Static HTML.

The page repeats each plan tier twice (desktop/mobile responsive blocks),
so we deduplicate by plan name (Small/Medium/Large).
"""
import re

from scraper.base import fetch_static
from scraper.schema import MobilePlan, now_iso

PROVIDER = "Vodafone"
URL = "https://www.vodafone.com.au/plans/sim-only"
REQUIRES_JS = False

# "65GB$58per month" -- the rendered text runs together without spaces
PLAN_RE = re.compile(r"(\d+)\s*GB\s*[$]\s*(\d+)\s*per\s+month", re.IGNORECASE)
# Promo end date for student offer: "from 23/01/2025 to 31/08/2026"
PROMO_DATE_RE = re.compile(r"to\s+(\d{2})/(\d{2})/(\d{4})")


def _parse_promo_end_date(text: str) -> str | None:
    """Extract 'to DD/MM/YYYY' from the student bonus offer."""
    match = PROMO_DATE_RE.search(text)
    if not match:
        return None
    day, month, year = match.groups()
    return f"{year}-{month}-{day}"


def scrape() -> list[MobilePlan]:
    soup = fetch_static(URL)
    text = soup.get_text(" ", strip=True)
    scraped_at = now_iso()

    # Find all plan+price pairs
    matches = PLAN_RE.findall(text)
    promo_end_date = _parse_promo_end_date(text)

    seen: set[str] = set()
    plans: list[MobilePlan] = []

    for gb_str, price_str in matches:
        tier_gb = int(gb_str)
        if tier_gb == 65:
            plan_name = "Small Plan"
        elif tier_gb == 220:
            plan_name = "Medium Plan"
        elif tier_gb == 420:
            plan_name = "Large Plan"
        else:
            continue

        if plan_name in seen:
            continue
        seen.add(plan_name)

        plans.append(
            MobilePlan(
                provider=PROVIDER,
                plan_name=plan_name,
                price_monthly=float(price_str),
                promo_price=None,
                promo_period_months=None,
                promo_end_date=promo_end_date,
                contract_length="Month-to-month",
                data_allowance_gb=float(tier_gb),
                is_unlimited_data=False,
                network=None,
                network_tech=None,
                source_url=URL,
                scraped_at=scraped_at,
            )
        )

    return plans