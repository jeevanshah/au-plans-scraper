"""Aussie Broadband SIM-only mobile plans scraper. Static HTML.

Cards use 'embla__slide' class (Embla carousel). AB mobile runs on Optus
network. Pricing: "$X /month first N months* ... $Y/month after promo period"
"""
import re

from scraper.base import fetch_static
from scraper.schema import MobilePlan, now_iso

PROVIDER = "Aussie Broadband"
URL = "https://www.aussiebroadband.com.au/mobile/sim-only-plans/"
REQUIRES_JS = False

GB_RE = re.compile(r"(\d+)\s*(?:[Gg][Bb])")
DOLLAR_RE = re.compile(r"\$\s*(\d+\.?\d*)")
# "$15 /month first 3 months" -- promo price + duration
PROMO_FIRST_RE = re.compile(
    r"\$\s*(\d+\.?\d*)\s*/month\s+first\s+(\d+)\s+months?", re.I
)
# "$30/month after promo period" -- regular price
AFTER_PROMO_RE = re.compile(
    r"\$\s*(\d+\.?\d*)\s*/month\s+after\s+promo\s+period", re.I
)


def scrape():
    soup = fetch_static(URL)
    scraped_at = now_iso()

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

        # Anchored promo extraction
        first_m = PROMO_FIRST_RE.search(txt)
        after_m = AFTER_PROMO_RE.search(txt)

        price_monthly = None
        promo_price = None
        promo_months = None

        # Extract prices explicitly associated with /month
        month_prices = re.findall(r"\$\s*(\d+\.?\d*)\s*/\s*month", txt, re.I)
        if after_m and first_m:
            price_monthly = float(after_m.group(1))
            promo_price = float(first_m.group(1))
            promo_months = int(first_m.group(2))
        elif month_prices:
            price_monthly = float(month_prices[0])
        else:
            prices = DOLLAR_RE.findall(txt)
            vals = sorted(set(float(p) for p in prices if 10 <= float(p) <= 150))
            if vals:
                price_monthly = vals[0]

        if price_monthly is None or price_monthly <= 1:
            continue

        if promo_price is not None and promo_price >= price_monthly:
            promo_price = None
            promo_months = None

        seen_gb.add(gb)
        plans.append(
            MobilePlan(
                provider=PROVIDER,
                plan_name="{}GB".format(int(gb)),
                price_monthly=price_monthly,
                promo_price=promo_price,
                promo_period_months=promo_months,
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