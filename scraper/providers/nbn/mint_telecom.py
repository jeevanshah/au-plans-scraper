"""Mint Telecom NBN plans scraper. Static HTML, no JS rendering needed.

Mint Telecom is a Hobart, Tasmania-based regional telecommunications provider
offering fixed-price NBN plans on a 6-month contract.
"""
import re

from scraper.base import fetch_static, normalize_nbn_speed_tier
from scraper.schema import NbnPlan, now_iso

PROVIDER = "Mint Telecom"
URL = "https://minttelecom.com.au/plans/Fibre-to-the-Premise-Hybrid-Fibre-Coaxial"
REQUIRES_JS = False

SPEED_RE = re.compile(r"(\d+)/(\d+)")
EVENING_RE = re.compile(r"(\d+)\s*Mbps\s*down", re.I)


def scrape() -> list[NbnPlan]:
    soup = fetch_static(URL)
    scraped_at = now_iso()

    cards = soup.find_all("div", class_="planInner")
    plans: list[NbnPlan] = []
    seen_tiers: set[str] = set()

    for card in cards:
        name_el = card.find("div", class_="planName")
        marketing_name = name_el.get_text(strip=True) if name_el else "NBN"

        # Price
        price_d = card.find("span", class_="priceD")
        price_c = card.find("span", class_="priceC")
        if not price_d or not price_c:
            continue
        price_d_val = re.sub(r"[^\d]", "", price_d.get_text(strip=True))
        price_c_val = re.sub(r"[^\d]", "", price_c.get_text(strip=True))
        if not price_d_val:
            continue
        price_monthly = float(f"{price_d_val}.{price_c_val or '00'}")

        # Speed
        speed_spec = card.find("div", class_="speedSpecification")
        speed_txt = speed_spec.get_text(" ", strip=True) if speed_spec else ""
        m_speed = SPEED_RE.search(speed_txt)
        if not m_speed:
            continue
        raw_down = int(m_speed.group(1))
        raw_up = int(m_speed.group(2))

        speed_tier, _, _ = normalize_nbn_speed_tier(raw_down, raw_up)

        # Evening speed
        sub_title = card.find("div", class_="planSubTitle")
        sub_txt = sub_title.get_text(" ", strip=True) if sub_title else ""
        m_eve = EVENING_RE.search(sub_txt)
        evening_speed = float(m_eve.group(1)) if m_eve else float(raw_down)

        tech_type = "Fibre" if raw_down >= 500 else "Fibre and FTTN"

        if speed_tier in seen_tiers:
            continue
        seen_tiers.add(speed_tier)

        plans.append(
            NbnPlan(
                provider=PROVIDER,
                plan_name=f"{marketing_name} {speed_tier}",
                price_monthly=price_monthly,
                promo_price=None,
                promo_period_months=None,
                promo_end_date=None,
                contract_length="6-month contract",
                speed_tier=speed_tier,
                typical_evening_speed_mbps=evening_speed,
                tech_type=tech_type,
                source_url=URL,
                scraped_at=scraped_at,
            )
        )

    if not plans:
        raise RuntimeError("scrape() could not extract any plans from Mint Telecom page")
    return plans
