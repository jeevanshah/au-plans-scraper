"""Activ8me nbn Sky Muster Plus Premium satellite plans scraper. The plan cards are
rendered client-side (Next.js) even before an address is entered, so fetch_js is
needed -- fetch_static only sees the pre-hydration shell with no plan prices."""
import re

from scraper.base import fetch_js
from scraper.schema import SatellitePlan, now_iso

PROVIDER = "Activ8me"
URL = "https://www.activ8me.net.au/internet/skymuster"
REQUIRES_JS = True

CARD_RE = re.compile(
    r"(?P<name>Premium \d+)\s*nbn\s*.?\s*(?P<speed>\d+/\d+)\s*Unlimited Data Allowance\*\s*"
    r"\$(?P<price>[\d.]+)\s*/month"
)


def scrape() -> list[SatellitePlan]:
    soup = fetch_js(URL, wait_until="load", settle_ms=4000)
    text = soup.get_text(" ", strip=True)

    plans = []
    scraped_at = now_iso()
    seen_names = set()

    for match in CARD_RE.finditer(text):
        plan_name = match.group("name")
        if plan_name in seen_names:
            continue  # the selected plan's summary echoes further down the page
        seen_names.add(plan_name)

        speed_tier = match.group("speed")
        price_monthly = float(match.group("price"))

        plans.append(
            SatellitePlan(
                provider=PROVIDER,
                plan_name=f"{plan_name} ({speed_tier})",
                price_monthly=price_monthly,
                promo_price=None,
                promo_period_months=None,
                # Free standard installation, no dish/equipment charge disclosed --
                # only optional routers are sold separately, which aren't required.
                upfront_hardware_cost=None,
                data_allowance_gb=None,
                is_unlimited_data=True,
                network="Sky Muster",
                contract_length="Month-to-month contract",
                source_url=URL,
                scraped_at=scraped_at,
            )
        )
    return plans
