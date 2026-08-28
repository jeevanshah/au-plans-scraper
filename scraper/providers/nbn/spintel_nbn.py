"""SpinTel NBN plans scraper. Static HTML.

Pricing: "$X Per Month For N months, then $Y ongoing" / "$X /month for N months then $Y ongoing" pattern.
Targets the maximum savings WhistleOut partner LP (https://www.spintel.net.au/lp/home/nbn-wo),
with automatic fallback to the direct NBN page if unavailable.
"""
import logging
import re

from scraper.base import classify_tech_type, fetch_static, normalize_nbn_speed_tier
from scraper.schema import NbnPlan, now_iso

logger = logging.getLogger("scraper.spintel_nbn")

PROVIDER = "SpinTel"
URL = "https://www.spintel.net.au/lp/home/nbn-wo"
DIRECT_URL = "https://www.spintel.net.au/nbn"
REQUIRES_JS = False

SPEED_RE = re.compile(r"(\d+)/(\d+)\s*Mbps", re.I)
# "$59 Per Month For 6 months, then $69.95 ongoing" or "$41 /month for 6 months then $69.95 ongoing"
FOR_N_THEN_RE = re.compile(
    r"\$\s*(\d+\.?\d*)\s*(?:/\s*month|[Pp]er\s+[Mm]onth)\s+[Ff]or\s+(\d+)\s+months?\s*,?\s*then\s+\$\s*(\d+\.?\d*)",
    re.I,
)
OFFER_ENDS_RE = re.compile(
    r"[Oo]ffer\s+[Ee]nds\s+(\d{1,2})\.(\d{2})\.(\d{2})", re.I
)
TYPICAL_RE = re.compile(r"Typical evening speed[^\d]*(\d+)(?:/(\d+))?\s*Mbps", re.I)

# Direct public promotional prices for comparison when partner LP is cheaper
DIRECT_PROMO_PRICES = {
    "NBN 25/10": 44.0,
    "NBN 750/50": 84.0,
}


def _parse_plans_from_soup(soup, source_url: str) -> list[NbnPlan]:
    scraped_at = now_iso()
    text = soup.get_text(" ", strip=True)
    is_partner = "nbn-wo" in source_url

    plans = []
    seen_tiers = set()

    for m in SPEED_RE.finditer(text):
        down, up = m.groups()
        tier, _, _ = normalize_nbn_speed_tier(down, up)

        # Dedup on normalized speed tier (e.g. NBN 1000/100)
        if tier in seen_tiers:
            continue

        start = m.start()
        end = min(start + 350, len(text))
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
            promo_end_date = f"20{y}-{mm}-{d}"

        if regular_price <= 1:
            continue

        typ_m = TYPICAL_RE.search(window)
        evening_speed = float(typ_m.group(1)) if typ_m else float(down)

        has_promo = promo_price < regular_price
        seen_tiers.add(tier)

        deal_channel = "partner_exclusive" if is_partner else "direct"
        deal_channel_label = "WhistleOut Special" if is_partner else "Direct Public Offer"
        direct_promo = DIRECT_PROMO_PRICES.get(tier) if is_partner else None
        how_to_get = (
            "Discounted via SpinTel's WhistleOut partner campaign. Saves an extra $3/mo for 6 months compared to the direct website."
            if is_partner
            else None
        )
        direct_url = DIRECT_URL if is_partner else None

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
                typical_evening_speed_mbps=evening_speed,
                tech_type=classify_tech_type(window),
                deal_channel=deal_channel,
                deal_channel_label=deal_channel_label,
                direct_public_promo_price=direct_promo,
                how_to_get=how_to_get,
                direct_url=direct_url,
                source_url=source_url,
                scraped_at=scraped_at,
            )
        )

    return plans


def scrape(url: str | None = None) -> list[NbnPlan]:
    target_url = url or URL
    try:
        soup = fetch_static(target_url)
        plans = _parse_plans_from_soup(soup, target_url)
        if plans:
            return plans
    except Exception as exc:
        logger.warning("Failed to scrape SpinTel primary URL %s: %s", target_url, exc)

    if target_url != DIRECT_URL and url is None:
        logger.info("Falling back to SpinTel direct URL %s", DIRECT_URL)
        soup = fetch_static(DIRECT_URL)
        plans = _parse_plans_from_soup(soup, DIRECT_URL)
        if plans:
            return plans

    raise RuntimeError("scrape() returned no plans")