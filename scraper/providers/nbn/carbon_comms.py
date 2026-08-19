"""Carbon Comms NBN plans scraper. JS-rendered Shopify store -- needs fetch_js()."""
import re

from scraper.base import fetch_js
from scraper.schema import NbnPlan, now_iso

PROVIDER = "Carbon Comms"
URL = "https://carboncomms.com.au/pages/carbon-comms-nbn-plans"
REQUIRES_JS = True

SPEED_RE = re.compile(r"(\d+)/(\d+)\s*Mbps", re.IGNORECASE)
TYPICAL_RE = re.compile(r"Typical evening speed:\s*(\d+)\s*Mbps", re.IGNORECASE)
PRICE_RE = re.compile(r"\$(\d+(?:\.\d+)?)\s*/\s*month", re.IGNORECASE)


def scrape() -> list[NbnPlan]:
    soup = fetch_js(URL, settle_ms=4000)
    scraped_at = now_iso()

    plans = []
    seen = set()

    # Find plan card blocks
    for card in soup.find_all(True):
        txt = card.get_text(" ", strip=True)
        if "SIGN ME UP" in txt and "Typical evening speed" in txt and len(txt) < 400:
            speed_m = SPEED_RE.search(txt)
            price_m = PRICE_RE.search(txt)
            if not speed_m or not price_m:
                continue

            down_mbps = speed_m.group(1)
            up_mbps = speed_m.group(2)
            speed_tier = f"NBN {down_mbps}/{up_mbps}"

            if speed_tier in seen:
                continue
            seen.add(speed_tier)

            price = float(price_m.group(1))
            typical_m = TYPICAL_RE.search(txt)
            typical_speed = float(typical_m.group(1)) if typical_m else float(down_mbps)

            name_m = re.search(r"(Carbon\s+[A-Za-z0-9\s/]+?nbn)", txt, re.IGNORECASE)
            plan_name = name_m.group(1).replace("?", "").strip() if name_m else f"Carbon NBN {down_mbps}/{up_mbps}"

            tech_type = "HFC and FTTP" if "HFC & FTTP" in txt else ("HFC" if "HFC Services" in txt else "Fixed Line")

            plans.append(
                NbnPlan(
                    provider=PROVIDER,
                    plan_name=plan_name,
                    price_monthly=price,
                    promo_price=None,
                    promo_period_months=None,
                    contract_length="No lock-in contract",
                    speed_tier=speed_tier,
                    typical_evening_speed_mbps=typical_speed,
                    tech_type=tech_type,
                    source_url=URL,
                    scraped_at=scraped_at,
                )
            )

    return plans
