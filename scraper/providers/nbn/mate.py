"""Mate Communicate NBN plans scraper.

Scrapes live residential NBN plans from https://www.letsbemates.com.au/nbn/
Extracts regular prices, 6-month promotional discounts, promo codes,
and measured typical evening speeds.
"""
import re

from scraper.base import fetch_static, normalize_nbn_speed_tier
from scraper.schema import NbnPlan, now_iso

PROVIDER = "Mate"
URL = "https://www.letsbemates.com.au/nbn/"
REQUIRES_JS = False

TIER_NAME_RE = re.compile(r"([A-Za-z'’\s]+)\s+nbn®\s+(\d+/\d+)")
SPEED_RE = re.compile(r"(\d+)\s*Mbps\s+Download speed", re.I)
PRICE_RE = re.compile(r"\$(\d+)\s+\$(\d+)\s+per month.*?reverts to\s+\$(\d+)")
SINGLE_PRICE_RE = re.compile(r"\$(\d+)\s+per month")
PROMO_CODE_RE = re.compile(r"promo code\s+([A-Z0-9]+)")


def scrape() -> list[NbnPlan]:
    soup = fetch_static(URL)
    scraped_at = now_iso()

    slides = soup.find_all("div", class_=lambda c: c and "nbn-slide-item" in c)
    plans: list[NbnPlan] = []
    seen_tiers: set[str] = set()

    for slide in slides:
        text = slide.get_text(" ", strip=True)

        m_name = TIER_NAME_RE.search(text)
        if not m_name:
            continue

        marketing_name = m_name.group(1).strip()
        speed_raw = m_name.group(2).strip()

        # Skip fixed wireless / satellite plans for standard fixed-line NBN
        if "wireless" in marketing_name.lower() or "satellite" in marketing_name.lower():
            continue

        m_down, m_up = speed_raw.split("/")
        raw_down = int(m_down)
        raw_up = int(m_up)

        # Drop Mate DOM typo card "2000/100" (NBN wholesale 2000 Mbps tier is 2000/200)
        if raw_down == 2000 and raw_up == 100:
            continue

        speed_tier, _, _ = normalize_nbn_speed_tier(raw_down, raw_up)

        # Evening speed
        m_eve = SPEED_RE.search(text)
        evening_speed = float(m_eve.group(1)) if m_eve else float(raw_down)

        # Pricing
        m_price = PRICE_RE.search(text)
        if m_price:
            regular_price = float(m_price.group(1))
            promo_price = float(m_price.group(2))
            promo_months = 6
        else:
            m_single = SINGLE_PRICE_RE.search(text)
            if not m_single:
                continue
            regular_price = float(m_single.group(1))
            promo_price = None
            promo_months = None

        m_code = PROMO_CODE_RE.search(text)
        promo_code = m_code.group(1) if m_code else None

        # Build plan title
        title = f"{marketing_name} {speed_tier}"
        if promo_code and promo_price:
            title = f"{title} (code {promo_code})"

        tech_type = "Fibre" if raw_down >= 500 else "Fibre and FTTN"

        if speed_tier in seen_tiers:
            continue
        seen_tiers.add(speed_tier)

        plans.append(
            NbnPlan(
                provider=PROVIDER,
                plan_name=title,
                price_monthly=regular_price,
                promo_price=promo_price,
                promo_period_months=promo_months,
                promo_end_date="2026-12-31" if promo_price else None,
                contract_length="No lock-in contract",
                speed_tier=speed_tier,
                typical_evening_speed_mbps=evening_speed,
                tech_type=tech_type,
                source_url=URL,
                scraped_at=scraped_at,
            )
        )

    if not plans:
        raise RuntimeError("scrape() could not extract any plans from Mate NBN page")
    return plans
