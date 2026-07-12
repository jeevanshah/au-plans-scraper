"""TPG NBN plans scraper. Static HTML (React SSR)."""
import re

from scraper.base import classify_tech_type, fetch_static
from scraper.schema import NbnPlan, now_iso

PROVIDER = "TPG"
URL = "https://www.tpg.com.au/nbn"
REQUIRES_JS = False

NBN_LABEL_RE = re.compile(r"\b(?:NBN|nbn)\s*(\d+)(?:/(\d+))?", re.I)
FOR_N_THEN_RE = re.compile(
    r"[Ff]or\s+(?:the\s+)?first\s+(\d+)\s+months.*?then\s+\$\s*(\d+\.?\d*)/mth", re.I
)
PRICE_MTH_RE = re.compile(r"\$\s*(\d+\.?\d*)/mth", re.I)


def scrape():
    soup = fetch_static(URL)
    scraped_at = now_iso()
    text = soup.get_text(" ", strip=True)

    plans = []
    seen_tiers = set()

    for nbn_m in NBN_LABEL_RE.finditer(text):
        down = nbn_m.group(1)
        up = nbn_m.group(2) if nbn_m.group(2) else down
        tier = f"NBN {down}/{up}"
        if tier in seen_tiers:
            continue

        window_start = nbn_m.start()
        window_end = min(nbn_m.end() + 400, len(text))
        window = text[window_start:window_end]

        fn_m = FOR_N_THEN_RE.search(window)
        prices = PRICE_MTH_RE.findall(window)
        vals = sorted(set(float(p) for p in prices if float(p) > 1))
        plan_vals = [v for v in vals if v >= 50]

        regular_price = None
        promo_price = None
        promo_months = None

        if fn_m:
            then_price = float(fn_m.group(2))
            if then_price >= 50:
                regular_price = then_price
                promo_months = int(fn_m.group(1))
                for v in plan_vals:
                    if v < then_price:
                        promo_price = v
                        break
        elif plan_vals:
            regular_price = plan_vals[-1]

        if regular_price is None or regular_price <= 1:
            continue

        seen_tiers.add(tier)
        plans.append(
            NbnPlan(
                provider=PROVIDER,
                plan_name=tier,
                price_monthly=regular_price,
                promo_price=(promo_price if promo_price and promo_price < regular_price else None),
                promo_period_months=(promo_months if promo_price and promo_price < regular_price else None),
                contract_length="No lock-in contract",
                speed_tier=tier,
                tech_type=classify_tech_type(window),
                source_url=URL,
                scraped_at=scraped_at,
            )
        )

    if not plans:
        raise RuntimeError("scrape() returned no plans")
    return plans