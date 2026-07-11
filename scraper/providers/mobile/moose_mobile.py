"""Moose Mobile SIM-only plans scraper.

The root domain is a JS-rendered SPA with sparse static HTML (3.6K chars).
Needs Playwright fetch_js to render plan content. Moose runs on the Vodafone
network.
"""
import re

from scraper.base import fetch_js
from scraper.schema import MobilePlan, now_iso

PROVIDER = "Moose Mobile"
URL = "https://www.moosemobile.com.au/"
REQUIRES_JS = True

GB_RE = re.compile(r"(\d+)\s*GB", re.I)
DOLLAR_RE = re.compile(r"\$\s*(\d+\.?\d*)")
MONTHLY_RE = re.compile(r"per\s+month|/mth|/month", re.I)


def scrape():
    soup = fetch_js(URL, settle_ms=5000)
    scraped_at = now_iso()
    text = soup.get_text(" ", strip=True)

    plans = []
    seen_gb = set()

    # Find plan cards — Moose uses card-like divs
    for tag in soup.find_all(["div", "article", "section"]):
        txt = tag.get_text(" ", strip=True)
        if len(txt) < 40 or len(txt) > 600:
            continue
        if "GB" not in txt or "$" not in txt:
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

        seen_gb.add(gb)
        plans.append(
            MobilePlan(
                provider=PROVIDER,
                plan_name="{}GB".format(int(gb)),
                price_monthly=price_monthly,
                promo_price=promo_price if promo_price and promo_price < price_monthly else None,
                promo_period_months=3 if (promo_price and promo_price < price_monthly) else None,
                promo_end_date=None,
                contract_length="Month-to-month",
                data_allowance_gb=gb,
                is_unlimited_data=False,
                network="Vodafone",
                network_tech=None,
                source_url=URL,
                scraped_at=scraped_at,
            )
        )

    return plans