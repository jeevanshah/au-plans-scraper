"""Flip NBN plans scraper. JS-rendered SPA at flipconnect.com.au.

Pure React SPA — needs fetch_js() to render. Flip is a budget NBN provider
offering plans with senior/pensioner/DVA discount variants.
"""
import re

from scraper.base import classify_tech_type, fetch_js
from scraper.schema import NbnPlan, now_iso

PROVIDER = "Flip"
URL = "https://www.flipconnect.com.au/"
REQUIRES_JS = True

SPEED_RE = re.compile(r"(?:NBN|nbn)\s*(\d+)(?:/(\d+))?", re.I)
PRICE_RE = re.compile(r"\$\s*(\d+\.?\d*)")
MBPS_RE = re.compile(r"(\d+)\s*Mbps", re.I)


def scrape():
    soup = fetch_js(URL, settle_ms=6000)
    scraped_at = now_iso()
    text = soup.get_text(" ", strip=True)

    plans = []
    seen_tiers = set()

    # Flip renders plan cards with NBN speed labels
    for tag in soup.find_all(["div", "section", "article"]):
        txt = tag.get_text(" ", strip=True)
        if len(txt) < 30 or len(txt) > 600:
            continue

        speed_m = SPEED_RE.search(txt)
        if not speed_m:
            continue

        down = speed_m.group(1)
        up = speed_m.group(2) if speed_m.group(2) else down
        speed_tier = "NBN {}/{}".format(down, up)

        if speed_tier in seen_tiers:
            continue
        seen_tiers.add(speed_tier)

        prices = PRICE_RE.findall(txt)
        vals = sorted(set(float(p) for p in prices if float(p) > 1))

        regular_price = None
        promo_price = None

        if len(vals) >= 2:
            promo_price = vals[0]
            regular_price = vals[1]
        elif vals:
            regular_price = vals[0]

        if regular_price is None or regular_price <= 1:
            continue

        plans.append(
            NbnPlan(
                provider=PROVIDER,
                plan_name=speed_tier,
                price_monthly=regular_price,
                promo_price=promo_price if promo_price and promo_price < regular_price else None,
                promo_period_months=6 if (promo_price and promo_price < regular_price) else None,
                contract_length="No lock-in contract",
                speed_tier=speed_tier,
                tech_type=classify_tech_type(txt),
                source_url=URL,
                scraped_at=scraped_at,
            )
        )

    return plans