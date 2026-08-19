"""Swoop OptiComm plans scraper."""
import re
from bs4 import BeautifulSoup

from scraper.base import fetch_static
from scraper.schema import OpticommPlan, now_iso

PROVIDER = "Swoop"
URL = "https://www.swoop.com.au/opticomm/"
REQUIRES_JS = False

SPEED_RE = re.compile(r"(\d+)/(\d+)\s*Mbps", re.IGNORECASE)
PRICE_RE = re.compile(r"\$(\d+)\s*\$(\d+)\s*per month\s*\$(\d+)/mth off for (\d+)\s*months", re.IGNORECASE)
SIMPLE_PRICE_RE = re.compile(r"\$(\d+)\s*(?:/mth|per month)", re.IGNORECASE)


def scrape() -> list[OpticommPlan]:
    soup = fetch_static(URL)
    scraped_at = now_iso()

    plans = []
    # Swoop plan cards on /opticomm/
    cards = soup.find_all(class_=lambda c: c and ("plan-card" in c.lower() or "pricing-card" in c.lower() or "plan_box" in c.lower()))
    
    if not cards:
        # Fallback to finding container sections
        sections = soup.find_all(["div", "section"])
        for sec in sections:
            txt = sec.get_text(" ", strip=True)
            if "Opticomm Fibre" in txt and "per month" in txt and len(txt) < 350:
                cards.append(sec)

    seen_tiers = set()
    for card in cards:
        txt = card.get_text(" ", strip=True)
        speed_m = SPEED_RE.search(txt)
        if not speed_m:
            continue
        down_mbps, up_mbps = speed_m.group(1), speed_m.group(2)
        speed_tier = f"OptiComm {down_mbps}/{up_mbps}"
        if speed_tier in seen_tiers:
            continue

        promo_m = PRICE_RE.search(txt)
        if promo_m:
            regular_price = float(promo_m.group(1))
            promo_price = float(promo_m.group(2))
            promo_months = int(promo_m.group(4))
        else:
            p_m = SIMPLE_PRICE_RE.search(txt)
            if not p_m:
                continue
            regular_price = float(p_m.group(1))
            promo_price = None
            promo_months = None

        seen_tiers.add(speed_tier)
        plans.append(
            OpticommPlan(
                provider=PROVIDER,
                plan_name=f"Opticomm Fibre {down_mbps}/{up_mbps}",
                price_monthly=regular_price,
                promo_price=promo_price,
                promo_period_months=promo_months,
                contract_length="No lock-in contract",
                speed_tier=speed_tier,
                typical_evening_speed_mbps=float(down_mbps),
                tech_type="Fibre",
                source_url=URL,
                scraped_at=scraped_at,
            )
        )

    return plans
