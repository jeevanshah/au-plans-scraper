"""SpinTel NBN plans scraper. Static HTML.

Pricing: "$X Per Month For N months, then $Y ongoing" pattern.
Dedup on download speed to avoid duplicate tiers from typical evening vs
max speed labels in same card.
"""
import re

from scraper.base import classify_tech_type, fetch_static, normalize_nbn_speed_tier
from scraper.schema import NbnPlan, now_iso

PROVIDER = "SpinTel"
URL = "https://www.spintel.net.au/nbn"
REQUIRES_JS = False

SPEED_RE = re.compile(r"(\d+)/(\d+)\s*Mbps", re.I)
# "$59 Per Month For 6 months, then $69.95 ongoing"
FOR_N_THEN_RE = re.compile(
    r"\$\s*(\d+\.?\d*)\s*[Pp]er\s+[Mm]onth\s+[Ff]or\s+(\d+)\s+months?\s*,?\s*then\s+\$\s*(\d+\.?\d*)", re.I
)
OFFER_ENDS_RE = re.compile(
    r"[Oo]ffer\s+[Ee]nds\s+(\d{1,2})\.(\d{2})\.(\d{2})", re.I
)


def scrape():
    soup = fetch_static(URL)
    scraped_at = now_iso()
    text = soup.get_text(" ", strip=True)

    plans = []
    seen_tiers = set()

    for m in SPEED_RE.finditer(text):
        down, up = m.groups()
        tier, evening_d, evening_u = normalize_nbn_speed_tier(down, up)

        # Dedup on normalized speed tier (e.g. NBN 1000/100)
        if tier in seen_tiers:
            continue

        start = m.start()
        end = min(start + 300, len(text))
        window = text[start:end]

        fn_m = FOR_N_THEN_RE.search(window)
        if not fn_m:
            continue

        promo_price = float(fn_m.group(1))
        promo_months = int(fn_m.group(2))
        regular_price = float(fn_m.group(3))

        offer_m = OFFER_ENDS_RE.search(window)
        promo_end_date = None
        if offer_m:
            d, mm, y = offer_m.groups()
            promo_end_date = "20{}-{}-{}".format(y, mm, d)

        if regular_price <= 1:
            continue

        has_promo = promo_price < regular_price
        seen_tiers.add(tier)
        plans.append(
            NbnPlan(
                provider=PROVIDER,
                plan_name=tier,
                price_monthly=regular_price,
                promo_price=promo_price if has_promo else None,
                promo_period_months=promo_months if has_promo else None,
                promo_end_date=promo_end_date if has_promo else None,
                contract_length="No lock-in contract",
                speed_tier=tier,
                typical_evening_speed_mbps=evening_d if evening_d and evening_d != float(tier.split()[1].split("/")[0]) else None,
                tech_type=classify_tech_type(window),
                source_url=URL,
                scraped_at=scraped_at,
            )
        )

    if not plans:
        raise RuntimeError("scrape() returned no plans")
    return plans