"""Vodafone NBN plans scraper. Static HTML (React/styled-components).

Cards contain "Mbps Typical evening speed" + "$X Per month $Y" paired pricing.
Uses page-level text pattern matching since card classes are generated hashes.
"""
import re

from scraper.base import classify_tech_type, fetch_static
from scraper.schema import NbnPlan, now_iso

PROVIDER = "Vodafone"
URL = "https://www.vodafone.com.au/home-internet/nbn"
REQUIRES_JS = False

# "$ 89 Per month $ 104" — promo then regular
PRICE_PAIRED_RE = re.compile(
    r"(\d+)\s*Mbps.*?\$\s*(\d+)\s*[Pp]er\s+month\s+\$\s*(\d+)", re.I
)
PROMO_MONTHS_RE = re.compile(
    r"(?:save|off)\s+\$?\d+/?mth\s+for\s+(\d+)\s+months?", re.I
)

MBPS_TO_TIER = {
    98: "NBN 100/20",
    500: "NBN 500/50",
    740: "NBN 1000/50",
}


def scrape():
    soup = fetch_static(URL)
    scraped_at = now_iso()
    text = soup.get_text(" ", strip=True)

    plans = []
    seen_mbps = set()

    # Combined pattern: "740 Mbps ... $89 Per month $104"
    for m in PRICE_PAIRED_RE.finditer(text):
        mbps = int(m.group(1))
        if mbps in seen_mbps:
            continue

        speed_tier = MBPS_TO_TIER.get(mbps)
        if not speed_tier:
            continue

        promo_val = float(m.group(2))
        regular_val = float(m.group(3))

        pm_m = PROMO_MONTHS_RE.search(text)
        promo_months = int(pm_m.group(1)) if pm_m else None

        seen_mbps.add(mbps)
        # Window context for tech_type
        ctx_start = max(0, m.start() - 20)
        ctx_end = min(len(text), m.end() + 100)
        ctx = text[ctx_start:ctx_end]

        plans.append(
            NbnPlan(
                provider=PROVIDER,
                plan_name=speed_tier,
                price_monthly=regular_val,
                promo_price=promo_val,
                promo_period_months=promo_months,
                contract_length="Month-to-month",
                speed_tier=speed_tier,
                typical_evening_speed_mbps=float(mbps),
                tech_type=classify_tech_type(ctx),
                source_url=URL,
                scraped_at=scraped_at,
            )
        )

    if not plans:
        raise RuntimeError("scrape() returned no plans")
    return plans