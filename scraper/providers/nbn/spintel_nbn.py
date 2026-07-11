"""SpinTel NBN plans scraper. Static HTML.

SpinTel is a budget NBN provider (WhistleOut "Best Fast NBN Provider").
Cards use w-col-option / plan-block classes with speed text and pricing.
"""
import re

from scraper.base import classify_tech_type, fetch_static
from scraper.schema import NbnPlan, now_iso

PROVIDER = "SpinTel"
URL = "https://www.spintel.net.au/nbn"
REQUIRES_JS = False

# "Home Starter 25/10 Mbps Typical evening speed 25/8 Mbps $59 Per Month For 6 months, then $69.95"
SPEED_RE = re.compile(r"(\d+)/(\d+)\s*Mbps", re.I)
PRICE_RE = re.compile(r"\$\s*(\d+\.?\d*)")
PROMO_MONTHS_RE = re.compile(r"[Ff]or\s+(\d+)\s+months?", re.I)
OFFER_ENDS_RE = re.compile(
    r"[Oo]ffer\s+[Ee]nds\s+(\d{1,2})\.(\d{2})\.(\d{2})", re.I
)


def scrape():
    soup = fetch_static(URL)
    scraped_at = now_iso()
    text = soup.get_text(" ", strip=True)

    plans = []
    seen_tiers = set()

    # SpinTel plan cards use w-col-option / plan-block classes
    for card in soup.find_all(class_=lambda c: c and "plan-block" in " ".join(c)):
        txt = card.get_text(" ", strip=True)
        if len(txt) < 30:
            continue

        speed_m = SPEED_RE.search(txt)
        if not speed_m:
            continue

        down, up = speed_m.groups()
        speed_tier = "NBN {}/{}".format(down, up)

        if speed_tier in seen_tiers:
            continue

        # Skip wireless/home starter names that aren't NBN plans
        if "wireless" in txt.lower() or "starter" in txt.lower():
            continue

        prices = PRICE_RE.findall(txt)
        if not prices:
            continue

        vals = sorted(set(float(p) for p in prices if float(p) > 1))
        promo_months_m = PROMO_MONTHS_RE.search(txt)

        regular_price = None
        promo_price = None
        promo_months = None

        if len(vals) >= 2:
            promo_price = vals[0]
            regular_price = vals[1]
        elif vals:
            regular_price = vals[0]

        if regular_price is None or regular_price <= 1:
            continue

        if promo_months_m:
            promo_months = int(promo_months_m.group(1))

        # Parse offer end date
        offer_m = OFFER_ENDS_RE.search(txt)
        promo_end_date = None
        if offer_m:
            d, m, y = offer_m.groups()
            promo_end_date = "20{}-{}-{}".format(y, m, d)

        seen_tiers.add(speed_tier)

        plans.append(
            NbnPlan(
                provider=PROVIDER,
                plan_name=speed_tier,
                price_monthly=regular_price,
                promo_price=promo_price if promo_price and promo_price < regular_price else None,
                promo_period_months=promo_months if (promo_price and promo_price < regular_price) else None,
                promo_end_date=promo_end_date,
                contract_length="No lock-in contract",
                speed_tier=speed_tier,
                tech_type=classify_tech_type(txt),
                source_url=URL,
                scraped_at=scraped_at,
            )
        )

    return plans