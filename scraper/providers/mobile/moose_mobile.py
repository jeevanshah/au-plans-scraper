"""Moose Mobile SIM-only plans scraper. JS-rendered SPA -- needs fetch_js().

Moose runs on the Vodafone network. Plan cards are Swiper.js carousel
slides with the `card-mobile` class -- a precise, real DOM anchor (not the
old page-wide div/article/section scan by text length). GB allowance is in
`.card-mobile__header .h2`; price is in `.card-mobile__section.price .h3`
(a "$X.XX" string followed by a `.fineprint` "/mth" span).

Needs a longer settle_ms than the original attempt used -- the plan cards
render a couple of seconds after the page's "load" event fires, so a
shorter wait previously captured the page before they existed at all.

No promo/discount pricing structure observed on these plans -- each tier is
a single flat monthly price, not a promo-then-regular pair.
"""
import re

from scraper.base import fetch_js
from scraper.schema import MobilePlan, now_iso

PROVIDER = "Moose Mobile"
URL = "https://moosemobile.com.au/"
REQUIRES_JS = True

GB_RE = re.compile(r"(\d+)\s*GB", re.I)
PRICE_RE = re.compile(r"\$\s*(\d+\.?\d*)")
NETWORK_TECH_RE = re.compile(r"(4G|5G)\s+Enabled", re.I)


def scrape() -> list[MobilePlan]:
    soup = fetch_js(URL, settle_ms=8000)
    scraped_at = now_iso()

    cards = soup.find_all("div", class_=lambda c: c and "card-mobile" in c)

    plans = []
    seen_gb = set()
    for card in cards:
        header = card.find(class_=lambda c: c and "card-mobile__header" in c)
        price_section = card.find(class_=lambda c: c and "price" in c)
        if not (header and price_section):
            continue

        gb_m = GB_RE.search(header.get_text(strip=True))
        price_m = PRICE_RE.search(price_section.get_text(" ", strip=True))
        if not (gb_m and price_m):
            continue

        gb = float(gb_m.group(1))
        if gb in seen_gb:
            continue
        price_monthly = float(price_m.group(1))
        if price_monthly <= 1:
            continue

        tech_m = NETWORK_TECH_RE.search(card.get_text(" ", strip=True))

        seen_gb.add(gb)
        plans.append(
            MobilePlan(
                provider=PROVIDER,
                plan_name=f"{int(gb)}GB",
                price_monthly=price_monthly,
                promo_price=None,
                promo_period_months=None,
                promo_end_date=None,
                contract_length="Month-to-month",
                data_allowance_gb=gb,
                is_unlimited_data=False,
                network="Vodafone",
                network_tech=tech_m.group(1) if tech_m else None,
                source_url=URL,
                scraped_at=scraped_at,
            )
        )

    if not plans:
        raise RuntimeError("scrape() returned no plans")
    return plans
