"""More Telecom NBN plans scraper. Static HTML, no JS rendering needed.

The four purchasable speed-tier cards are marked with a distinguishing
data-offer="false" attribute -- other same-class "card overflow-hidden
rounded-5" containers on the same page are actually router/modem add-on
cards and SIM cards (both marked data-offer="true" or with no data-offer
attribute at all), not NBN speed plans.

Prices and typical evening speeds render directly into the static HTML with
no address entry required (the "Check Address" button just checks
serviceability/order eligibility, not pricing gating) -- but each card's
authoritative nbn(R) speed tier (e.g. "500/50") only exists as text inside a
tooltip's data-bs-title attribute, not in any visible text node, so that one
field needs a regex over the card's raw HTML rather than its get_text().
Two more plans shown in the page's separate "Compare nbn(R) plans" table
(Fast 100/20, Fast Plus 100/40) have no matching buy-card/price at all in
this default (no-address) view, so they're not included here.
"""
import re

from scraper.base import fetch_static, parse_price
from scraper.schema import NbnPlan, now_iso

PROVIDER = "More Telecom"
URL = "https://www.more.com.au/personal/nbn-plans"
REQUIRES_JS = False

SPEED_TIER_RE = re.compile(r"nbn.\s*speed tier (\d+)/(\d+)")
TYPICAL_SPEED_RE = re.compile(r"([\d.]+)\s*Mbps\s*Download.*?([\d.]+)\s*Mbps\s*Upload", re.S)


def scrape() -> list[NbnPlan]:
    soup = fetch_static(URL)
    cards = soup.find_all("div", attrs={"data-offer": "false"})
    plans = []
    scraped_at = now_iso()

    for card in cards:
        name_el = card.find("p", class_="fs-4 fw-bold")
        price_el = card.find("div", class_="flex-wrap fw-semibold position-relative")
        tier_match = SPEED_TIER_RE.search(str(card))
        if not (name_el and price_el and tier_match):
            continue

        down_mbps, up_mbps = tier_match.groups()
        text = card.get_text(" ", strip=True)
        typical_match = TYPICAL_SPEED_RE.search(text)

        plans.append(
            NbnPlan(
                provider=PROVIDER,
                plan_name=name_el.get_text(strip=True),
                price_monthly=parse_price(price_el.get_text(strip=True)),
                promo_price=None,
                promo_period_months=None,
                contract_length="No lock-in contract",
                speed_tier=f"NBN {down_mbps}/{up_mbps}",
                typical_evening_speed_mbps=float(typical_match.group(1)) if typical_match else None,
                source_url=URL,
                scraped_at=scraped_at,
            )
        )
    return plans
