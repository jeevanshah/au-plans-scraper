"""Vodafone NBN plans scraper. Static HTML.

3 known tiers: Home Fast (98 Mbps → NBN 100/20), Home Superfast (500 Mbps →
NBN 500/50), Home Ultrafast (740 Mbps → NBN 1000/50). Plan-names read from
heading labels in page text.

Pricing: "$X Per month $Y" paired structure. Promo months extracted from
context near each tier match (not whole-page).
"""
import re

from scraper.base import classify_tech_type, fetch_static
from scraper.schema import NbnPlan, now_iso

PROVIDER = "Vodafone"
URL = "https://www.vodafone.com.au/home-internet/nbn"
REQUIRES_JS = False

# Known Vodafone Mbps values and their tier names
TIER_MAP = {
    98:  ("NBN 100/20", "Home Fast"),
    500: ("NBN 500/50", "Home Superfast"),
    740: ("NBN 1000/50", "Home Ultrafast"),
}

# "$X Per month $Y" within 2 lines of a Mbps value
PRICE_MBPS_RE = re.compile(
    r"(\d+)\s*Mbps\s+Typical\s+evening\s+speed.*?"
    r"\$\s*(\d+)\s*[Pp]er\s+month\s+\$\s*(\d+)", re.I
)
PROMO_MONTHS_RE = re.compile(
    r"(?:save|off)\s+\$?\d+/?mth\s+for\s+(\d+)\s+months?", re.I
)


def scrape():
    soup = fetch_static(URL)
    scraped_at = now_iso()
    text = soup.get_text(" ", strip=True)

    plans = []
    seen_mbps = set()

    for m in PRICE_MBPS_RE.finditer(text):
        mbps = int(m.group(1))

        # Only process known Vodafone tiers
        if mbps not in TIER_MAP:
            continue
        if mbps in seen_mbps:
            continue

        tier, plan_name = TIER_MAP[mbps]
        promo_val = float(m.group(2))
        regular_val = float(m.group(3))

        # Scope promo months to text window around this tier
        ctx_start = max(0, m.start() - 1000)
        ctx_end = min(len(text), m.end() + 1000)
        ctx = text[ctx_start:ctx_end]
        pm_m = PROMO_MONTHS_RE.search(ctx)
        promo_months = int(pm_m.group(1)) if pm_m else None

        seen_mbps.add(mbps)
        plans.append(
            NbnPlan(
                provider=PROVIDER,
                plan_name=plan_name,
                price_monthly=regular_val,
                promo_price=promo_val,
                promo_period_months=promo_months,
                contract_length="Month-to-month",
                speed_tier=tier,
                typical_evening_speed_mbps=float(mbps),
                tech_type=classify_tech_type(ctx),
                source_url=URL,
                scraped_at=scraped_at,
            )
        )

    if not plans:
        raise RuntimeError("scrape() returned no plans")
    return plans