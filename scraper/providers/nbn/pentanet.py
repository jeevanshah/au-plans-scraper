"""Pentanet NBN plans scraper. Static HTML, no JS rendering needed.

Pentanet is a Western Australia-headquartered ISP with local Perth infrastructure
(AS10214) peering locally at IX Australia WA (WAIX), EdgeIX Perth, and MegaIX Perth.
Their home NBN page embeds clean data attributes per plan card:
  - `data-price-0-base`: regular monthly price
  - `data-price-0-sale`: discounted promo price
  - `data-price-0-sale-duration`: promo duration in months
  - `.typical-speeds`: measured typical evening peak speeds
"""
import re

from scraper.base import fetch_static, normalize_nbn_speed_tier, parse_absolute_end_date
from scraper.schema import NbnPlan, now_iso

PROVIDER = "Pentanet"
URL = "https://pentanet.com.au/for-home/nbn"
REQUIRES_JS = False

OFFER_ENDS_RE = re.compile(r"Offer ends\s+(\d{1,2}\s+[A-Za-z]+\s+\d{4})", re.I)
TYPICAL_RE = re.compile(r"(\d+)\s*Mbps", re.I)


def scrape() -> list[NbnPlan]:
    soup = fetch_static(URL)
    scraped_at = now_iso()
    page_text = soup.get_text(" ", strip=True)

    promo_end_date = None
    offer_m = OFFER_ENDS_RE.search(page_text)
    if offer_m:
        promo_end_date = parse_absolute_end_date(f"Offer ends {offer_m.group(1)}")

    cards = soup.find_all("div", class_=lambda c: c and "gc-plan-nbn" in c and "gc-plan-home" in c)
    plans: list[NbnPlan] = []
    seen_tiers: set[str] = set()

    for card in cards:
        name_el = card.find("h3", class_="name")
        marketing_name = name_el.get_text(strip=True) if name_el else "NBN"

        price_el = card.find("h2", class_="value")
        if not price_el:
            continue

        base_price_str = price_el.get("data-price-0-base")
        sale_price_str = price_el.get("data-price-0-sale")
        duration_str = price_el.get("data-price-0-sale-duration")

        if not base_price_str:
            continue

        regular_price = float(base_price_str)
        promo_price = float(sale_price_str) if sale_price_str and float(sale_price_str) < regular_price else None
        promo_months = int(duration_str) if duration_str and promo_price else None

        down_el = card.find("div", class_="download")
        up_el = card.find("div", class_="upload")
        down_txt = down_el.find("span").get_text(strip=True) if down_el and down_el.find("span") else ""
        up_txt = up_el.find("span").get_text(strip=True) if up_el and up_el.find("span") else ""

        if not down_txt or not up_txt:
            continue

        raw_down = int(down_txt)
        raw_up = int(up_txt)
        speed_tier, _, _ = normalize_nbn_speed_tier(raw_down, raw_up)

        # Distinguish 100/20 vs 100/40 (Family vs Pro+)
        plan_key = f"{speed_tier}-{marketing_name}"
        if plan_key in seen_tiers:
            continue
        seen_tiers.add(plan_key)

        typ_el = card.find("div", class_="typical-speeds")
        typ_txt = typ_el.get_text(" ", strip=True) if typ_el else ""
        typ_m = TYPICAL_RE.search(typ_txt)
        evening_speed = float(typ_m.group(1)) if typ_m else float(raw_down)

        tech_type = "Fibre" if raw_down >= 500 else "Fibre and FTTN"

        plans.append(
            NbnPlan(
                provider=PROVIDER,
                plan_name=f"{marketing_name} {speed_tier}",
                price_monthly=regular_price,
                promo_price=promo_price,
                promo_period_months=promo_months,
                promo_end_date=promo_end_date if promo_price else None,
                contract_length="No lock-in contract",
                speed_tier=speed_tier,
                typical_evening_speed_mbps=evening_speed,
                tech_type=tech_type,
                source_url=URL,
                scraped_at=scraped_at,
            )
        )

    if not plans:
        raise RuntimeError("scrape() could not extract any plans from Pentanet NBN page")
    return plans
