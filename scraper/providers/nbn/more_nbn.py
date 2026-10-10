"""More Telecom NBN plans scraper. Static HTML, no JS rendering needed.

The four purchasable speed-tier cards are identified by containing both a plan
name heading (p.fs-4.fw-bold) and a price element (div.flex-wrap.fw-semibold.position-relative).

Prices and typical evening speeds render directly into the static HTML with
no address entry required. The authoritative nbn(R) speed tiers (e.g. 25/10,
50/20, 500/50, 1000/100) are extracted from the "Compare nbn(R) plans" table
on the same page (or fallback map), with legacy card tooltip regex support.
Two more plans shown in the page's comparison table (Fast 100/20, Fast Plus 100/40)
have no matching buy-card/price in this default view, so they are not included.
"""
import copy
import re

from bs4 import BeautifulSoup

from scraper.base import fetch_static, parse_price
from scraper.schema import NbnPlan, now_iso

PROVIDER = "More Telecom"
URL = "https://www.more.com.au/personal/nbn-plans"
REQUIRES_JS = False

SPEED_TIER_RE = re.compile(r"nbn.\s*speed tier (\d+)/(\d+)", re.IGNORECASE)
TYPICAL_SPEED_RE = re.compile(r"([\d.]+)\s*Mbps\s*Download.*?([\d.]+)\s*Mbps\s*Upload", re.S | re.IGNORECASE)

KNOWN_TIERS = {
    "Value": "NBN 25/10",
    "Value Plus": "NBN 50/20",
    "Fast": "NBN 100/20",
    "Fast Max": "NBN 500/50",
    "Fast Plus": "NBN 100/40",
    "Ultrafast": "NBN 1000/100",
}


def _extract_tier_map(soup: BeautifulSoup) -> dict[str, str]:
    """Extract plan name -> speed tier mapping from the comparison table."""
    tier_map: dict[str, str] = {}
    table = soup.find("table")
    if not table:
        return tier_map

    thead = table.find("thead")
    tbody = table.find("tbody")
    if not (thead and tbody):
        return tier_map

    headers = [th.get_text(strip=True) for th in thead.find_all("th")[1:]]
    rows = tbody.find_all("tr")
    if not rows:
        return tier_map

    tier_cells = []
    for td in rows[0].find_all("td")[1:]:
        td_copy = copy.copy(td)
        for s in td_copy.find_all("sup"):
            s.decompose()
        m = re.search(r"(\d+\s*/\s*\d+)", td_copy.get_text(strip=True))
        tier_cells.append(m.group(1).replace(" ", "") if m else None)

    for header, tier in zip(headers, tier_cells):
        if tier:
            tier_map[header] = f"NBN {tier}"

    return tier_map


def scrape() -> list[NbnPlan]:
    soup = fetch_static(URL)
    tier_map = _extract_tier_map(soup)
    cards = soup.find_all("div", attrs={"data-offer": True})
    plans = []
    scraped_at = now_iso()

    for card in cards:
        name_el = card.find("p", class_="fs-4 fw-bold")
        price_el = card.find("div", class_="flex-wrap fw-semibold position-relative")
        if not (name_el and price_el):
            continue

        plan_name = name_el.get_text(strip=True)
        tier_match = SPEED_TIER_RE.search(str(card))
        if tier_match:
            down_mbps, up_mbps = tier_match.groups()
            speed_tier = f"NBN {down_mbps}/{up_mbps}"
        elif plan_name in tier_map:
            speed_tier = tier_map[plan_name]
        elif plan_name in KNOWN_TIERS:
            speed_tier = KNOWN_TIERS[plan_name]
        else:
            continue

        text = card.get_text(" ", strip=True)
        typical_match = TYPICAL_SPEED_RE.search(text)

        plans.append(
            NbnPlan(
                provider=PROVIDER,
                plan_name=plan_name,
                price_monthly=parse_price(price_el.get_text(strip=True)),
                promo_price=None,
                promo_period_months=None,
                contract_length="No lock-in contract",
                speed_tier=speed_tier,
                typical_evening_speed_mbps=float(typical_match.group(1)) if typical_match else None,
                source_url=URL,
                scraped_at=scraped_at,
            )
        )
    return plans
