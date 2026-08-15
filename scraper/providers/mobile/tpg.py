"""TPG SIM-only mobile plans scraper.

Despite looking static at first glance, TPG's /mobile-plans page renders its
plan cards client-side -- fetch_js (Playwright) is required here.
"""
import re

from scraper.base import fetch_js
from scraper.schema import MobilePlan, now_iso

PROVIDER = "TPG"
URL = "https://www.tpg.com.au/mobile-plans"
REQUIRES_JS = True

HEADER_RE = re.compile(r"(\d+)GB\s+(\w+)\s+Plan")
PROMO_RE = re.compile(r"\$(\d+)\s*/mth\s*\.(\d+)\s*for (\d+) months?")
# The ongoing-price clause after the promo period, up to the next section --
# phrasing varies ("then $X or $Y with a TPG internet plan" vs "then $X with
# a linked TPG internet plan. Otherwise, $Y") so we grab everything between
# "then" and "Unlimited" and pick prices out of it rather than matching the
# whole clause literally.
TAIL_RE = re.compile(r"then\s+(.+?)\s+Unlimited", re.S)
DOLLAR_RE = re.compile(r"\$(\d+)/mth(\s+with a (?:linked )?TPG internet plan)?")
NETWORK_TECH_RE = re.compile(r"(4G|5G) network")


def _extract_standalone_price(tail: str) -> float | None:
    """Of the 1-2 ongoing prices in `tail`, return the one NOT tied to a bundle."""
    matches = DOLLAR_RE.findall(tail)
    if not matches:
        return None
    standalone = [value for value, bundle_marker in matches if not bundle_marker]
    chosen = standalone[0] if standalone else matches[0][0]
    return float(chosen)


def scrape() -> list[MobilePlan]:
    # Wait for the price text specifically, not just the card container -- the
    # card mounts before its price (fetched async) renders, so waiting on the
    # bare container risks capturing a skeleton with no $ amount yet.
    soup = fetch_js(URL, wait_selector=".plan__card:has-text('$')")
    cards = soup.find_all("div", class_=lambda c: c and "plan__card" in c)
    plans = []
    scraped_at = now_iso()

    for card in cards:
        text = card.get_text(" ", strip=True)
        header_match = HEADER_RE.search(text)
        promo_match = PROMO_RE.search(text)
        tail_match = TAIL_RE.search(text)
        if not (header_match and promo_match and tail_match):
            continue

        price_monthly = _extract_standalone_price(tail_match.group(1))
        if price_monthly is None:
            continue

        data_gb, tier_name = header_match.groups()
        promo_dollars, promo_cents, promo_months = promo_match.groups()
        network_tech_match = NETWORK_TECH_RE.search(text)

        plans.append(
            MobilePlan(
                provider=PROVIDER,
                plan_name=f"{tier_name} Plan",
                price_monthly=price_monthly,
                promo_price=float(f"{promo_dollars}.{promo_cents}"),
                promo_period_months=int(promo_months),
                contract_length="Month-to-month",
                data_allowance_gb=float(data_gb),
                is_unlimited_data=False,
                network=None,
                network_tech=network_tech_match.group(1) if network_tech_match else None,
                source_url=URL,
                scraped_at=scraped_at,
            )
        )
    return plans
