"""Vodafone NBN plans scraper. Static HTML.

Cards have generated class names like sc-24a45c1b-0/<hash>. Contains
Mbps speed text, $X per month pricing, and typical evening speed data.
"""
import re

from scraper.base import classify_tech_type, fetch_static
from scraper.schema import NbnPlan, now_iso

PROVIDER = "Vodafone"
URL = "https://www.vodafone.com.au/home-internet/nbn"
REQUIRES_JS = False

# "740 Mbps Typical evening speed (7pm-11pm) $ 89 Per month $ 104"
MBPS_RE = re.compile(r"(\d+)\s*Mbps", re.I)
PRICE_RE = re.compile(r"\$\s*(\d+)\s*[Pp]er\s+month", re.I)
SPEED_LABEL_RE = re.compile(r"(?:NBN|nbn)\s*(\d+)(?:/(\d+))?", re.I)
PROMO_MONTHS_RE = re.compile(r"off\s+for\s+(\d+)\s+months?", re.I)


def scrape():
    soup = fetch_static(URL)
    scraped_at = now_iso()
    text = soup.get_text(" ", strip=True)

    plans = []
    seen_tiers = set()

    # Vodafone cards have hash-style class names
    # Card blocks identified by having Mbps + $ Per month together
    for card in soup.find_all(class_=lambda c: c and "sc-24a45c1b" in " ".join(c)):
        txt = card.get_text(" ", strip=True)
        if len(txt) < 30:
            continue

        mbps_m = MBPS_RE.search(txt)
        if not mbps_m:
            continue

        mbps = int(mbps_m.group(1))

        # Vodafone tiers: 98, 500, 740 Mbps
        if mbps <= 100:
            speed_tier = "NBN 100/20"
        elif mbps <= 500:
            speed_tier = "NBN 500/50"
        else:
            speed_tier = "NBN 1000/50"

        if speed_tier in seen_tiers:
            continue
        seen_tiers.add(speed_tier)

        prices = PRICE_RE.findall(txt)
        if not prices:
            continue

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

        promo_months_m = PROMO_MONTHS_RE.search(text)
        promo_months = int(promo_months_m.group(1)) if promo_months_m else None

        plans.append(
            NbnPlan(
                provider=PROVIDER,
                plan_name=speed_tier,
                price_monthly=regular_price,
                promo_price=promo_price if promo_price and promo_price < regular_price else None,
                promo_period_months=promo_months if (promo_price and promo_price < regular_price) else None,
                contract_length="Month-to-month",
                speed_tier=speed_tier,
                typical_evening_speed_mbps=float(mbps),
                tech_type=classify_tech_type(txt),
                source_url=URL,
                scraped_at=scraped_at,
            )
        )

    return plans