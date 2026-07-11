"""Aussie Broadband SIM-only mobile plans scraper. Static HTML.

Cards use 'embla__slide' class containers. AB mobile runs on Optus network.
"""
import re

from scraper.base import fetch_static
from scraper.schema import MobilePlan, now_iso

PROVIDER = "Aussie Broadband"
URL = "https://www.aussiebroadband.com.au/mobile/sim-only-plans/"
REQUIRES_JS = False

GB_RE = re.compile(r"(\d+)\s*GB", re.I)
DOLLAR_RE = re.compile(r"\$\s*(\d+\.?\d*)")
PROMO_MONTHS_RE = re.compile(r"(?:first|for)\s+(\d+)\s+months?", re.I)


def scrape():
    soup = fetch_static(URL)
    scraped_at = now_iso()
    text = soup.get_text(" ", strip=True)

    plans = []
    seen_gb = set()

    for card in soup.find_all("div", class_="embla__slide"):
        txt = card.get_text(" ", strip=True)
        if len(txt) < 40:
            continue

        gb_match = GB_RE.search(txt)
        if not gb_match:
            continue
        gb = float(gb_match.group(1))
        if gb < 1 or gb in seen_gb:
            continue

        prices = DOLLAR_RE.findall(txt)
        vals = sorted(set(float(p) for p in prices if float(p) > 1))

        price_monthly = None
        promo_price = None

        if len(vals) >= 2:
            promo_price = vals[0]
            price_monthly = vals[1]
        elif vals:
            price_monthly = vals[0]

        if price_monthly is None or price_monthly <= 1:
            continue

        pm_m = PROMO_MONTHS_RE.search(txt)
        promo_months = int(pm_m.group(1)) if pm_m else None

        seen_gb.add(gb)
        plans.append(
            MobilePlan(
                provider=PROVIDER,
                plan_name="{}GB".format(int(gb)),
                price_monthly=price_monthly,
                promo_price=promo_price if promo_price and promo_price < price_monthly else None,
                promo_period_months=promo_months if (promo_price and promo_price < price_monthly) else None,
                promo_end_date=None,
                contract_length="Month-to-month",
                data_allowance_gb=gb,
                is_unlimited_data=False,
                network="Optus",
                network_tech=None,
                source_url=URL,
                scraped_at=scraped_at,
            )
        )

    return plans