"""Aussie Broadband NBN plans scraper. Static HTML, no JS rendering needed."""
import re

from scraper.base import classify_tech_type, fetch_static, parse_price
from scraper.schema import NbnPlan, now_iso

PROVIDER = "Aussie Broadband"
URL = "https://www.aussiebroadband.com.au/nbn-plans/"
REQUIRES_JS = False


def scrape() -> list[NbnPlan]:
    soup = fetch_static(URL)
    cards = soup.find_all("div", class_=lambda c: c and "group/card" in c)
    plans = []
    scraped_at = now_iso()

    for card in cards:
        text = card.get_text(" ", strip=True)
        if "Typical evening speed" not in text:
            continue  # skip hardware/router cards

        name_el = card.find("h3")
        speed_el = card.find("h4", class_=lambda c: c and "h3" in c)
        if not name_el or not speed_el:
            continue

        plan_name = name_el.get_text(strip=True)
        speed_tier = f"NBN {speed_el.get_text(strip=True)}"

        promo_match = re.search(r"first (\d+) months", text)
        regular_match = re.search(r"\$([\d.]+)/month after promo period", text)
        promo_price_el = card.find("strong", class_=lambda c: c and "text-3xl" in c)

        if regular_match:
            price_monthly = parse_price(regular_match.group(1))
            promo_price = parse_price(promo_price_el.get_text(strip=True)) if promo_price_el else None
            promo_period_months = int(promo_match.group(1)) if promo_match else None
        else:
            # no promo pricing shown -> the big price is the standing price
            price_monthly = parse_price(promo_price_el.get_text(strip=True))
            promo_price = None
            promo_period_months = None

        mbps = re.findall(r"(\d+)\s*Mbps", text)
        typical_evening_speed_mbps = float(mbps[0]) if mbps else None

        contract_length = "No lock-in contract" if "No lock-in contract" in text else "Contract required"

        tech_type = classify_tech_type(text)

        plans.append(
            NbnPlan(
                provider=PROVIDER,
                plan_name=plan_name,
                price_monthly=price_monthly,
                promo_price=promo_price,
                promo_period_months=promo_period_months,
                contract_length=contract_length,
                speed_tier=speed_tier,
                typical_evening_speed_mbps=typical_evening_speed_mbps,
                tech_type=tech_type,
                source_url=URL,
                scraped_at=scraped_at,
            )
        )
    return plans
