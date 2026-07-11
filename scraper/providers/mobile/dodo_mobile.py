"""Dodo SIM-only mobile plans scraper. Static HTML.

Dodo mobile runs on the Optus network. Cards use 'plan-tile' class.
"""
import re

from scraper.base import fetch_static
from scraper.schema import MobilePlan, now_iso

PROVIDER = "Dodo"
URL = "https://www.dodo.com/mobile"
REQUIRES_JS = False

GB_RE = re.compile(r"(\d+)\s*GB", re.I)
DOLLAR_RE = re.compile(r"\$\s*(\d+\.?\d*)")
OFFER_ENDS_RE = re.compile(
    r"[Oo]ffer\s+ends\s+(\d{1,2})\s+(January|February|March|April|May|June|"
    r"July|August|September|October|November|December)\s*(\d{4})?", re.I
)

MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}


def _parse_offer_end(text):
    m = OFFER_ENDS_RE.search(text)
    if not m:
        return None
    day, month_name, year = m.groups()
    return "{}-{:02d}-{:02d}".format(int(year) if year else 2026, MONTH_MAP[month_name.lower()], int(day))


def scrape():
    soup = fetch_static(URL)
    scraped_at = now_iso()
    text = soup.get_text(" ", strip=True)
    promo_end_date = _parse_offer_end(text)

    plans = []
    seen = set()

    for tile in soup.find_all("div", class_="plan-tile"):
        txt = tile.get_text(" ", strip=True)
        if len(txt) < 40:
            continue

        gb_match = GB_RE.search(txt)
        if not gb_match:
            continue
        gb = float(gb_match.group(1))
        if gb < 1 or gb in seen:
            continue

        prices = DOLLAR_RE.findall(txt)
        if not prices:
            continue

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

        seen.add(gb)
        plans.append(
            MobilePlan(
                provider=PROVIDER,
                plan_name="{}GB".format(int(gb)),
                price_monthly=price_monthly,
                promo_price=promo_price if promo_price and promo_price < price_monthly else None,
                promo_period_months=6 if (promo_price and promo_price < price_monthly) else None,
                promo_end_date=promo_end_date,
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