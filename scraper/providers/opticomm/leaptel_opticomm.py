"""Leaptel OptiComm plans scraper. JS-rendered -- needs fetch_js()."""
import re

from scraper.base import fetch_js
from scraper.schema import OpticommPlan, now_iso

PROVIDER = "Leaptel"
URL = "https://leaptel.com.au/opticomm-plans/"
REQUIRES_JS = True

SPEED_RE = re.compile(r"(\d+)Mbps\s*DOWNLOAD\s*(\d+)Mbps\s*UPLOAD", re.IGNORECASE)
TYPICAL_RE = re.compile(r"Typical evening speed:\s*([\d.]+)\s*/\s*([\d.]+)\*?\s*Mbps", re.IGNORECASE)
PRICE_PROMO_RE = re.compile(
    r"\$(\d+(?:\.\d+)?)\s*/\s*month\s*\$(\d+(?:\.\d+)?)\s*discount for (\d+)\s*months?,\s*then\s*\$([\d.]+)\s*ongoing",
    re.IGNORECASE,
)
PRICE_ONGOING_RE = re.compile(r"\$(\d+(?:\.\d+)?)\s*/\s*month", re.IGNORECASE)


def scrape() -> list[OpticommPlan]:
    soup = fetch_js(URL, settle_ms=5000)
    scraped_at = now_iso()

    ssr = soup.find(class_=lambda c: c and c == "wp-block-leaptel-plan-list__ssr")
    if ssr is None:
        raise RuntimeError("scrape() could not find the wp-block-leaptel-plan-list__ssr block")

    cards = ssr.find_all("div", class_=lambda c: c and c == "wp-block-leaptel-card")

    plans = []
    for card in cards:
        name_el = card.find("h3", class_="wp-block-leaptel-card__heading__title")
        if not name_el:
            continue
        plan_name = name_el.get_text(strip=True)
        text = card.get_text(" ", strip=True)

        speed_m = SPEED_RE.search(text)
        if not speed_m:
            continue
        down_mbps, up_mbps = speed_m.group(1), speed_m.group(2)
        speed_tier = f"OptiComm {down_mbps}/{up_mbps}"

        typical_m = TYPICAL_RE.search(text)
        typical_down = float(typical_m.group(1)) if typical_m else float(down_mbps)

        promo_m = PRICE_PROMO_RE.search(text)
        if promo_m:
            promo_price = float(promo_m.group(1))
            promo_months = int(promo_m.group(3))
            ongoing_price = float(promo_m.group(4))
        else:
            price_m = PRICE_ONGOING_RE.search(text)
            if not price_m:
                continue
            ongoing_price = float(price_m.group(1))
            promo_price = None
            promo_months = None

        plans.append(
            OpticommPlan(
                provider=PROVIDER,
                plan_name=plan_name,
                price_monthly=ongoing_price,
                promo_price=promo_price,
                promo_period_months=promo_months,
                contract_length="No lock-in contract",
                speed_tier=speed_tier,
                typical_evening_speed_mbps=typical_down,
                tech_type="Fibre",
                source_url=URL,
                scraped_at=scraped_at,
            )
        )

    return plans
