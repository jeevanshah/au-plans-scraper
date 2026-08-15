"""amaysim NBN plans scraper. Static AEM-rendered HTML, no JS needed.

amaysim offers NBN plans (powered by Optus wholesale network) across standard speed
tiers (NBN 25, 50, 100, 500, 750, 1000). The /nbn page renders them as
<article class="product-card product-card-nbnplans ..."> cards with data-* attributes
specifying original price, speeds, and technology (FTTP/HFC fibre vs all fixed-line).
"""
import re
from datetime import datetime

from scraper.base import fetch_static, parse_price
from scraper.schema import NbnPlan, now_iso

PROVIDER = "amaysim"
URL = "https://www.amaysim.com.au/nbn"
REQUIRES_JS = False

MONTH_MAP = {
    "January": 1, "February": 2, "March": 3, "April": 4,
    "May": 5, "June": 6, "July": 7, "August": 8,
    "September": 9, "October": 10, "November": 11, "December": 12,
}

END_DATE_RE = re.compile(r"offer ends\s+(\d+)\w*\s+([A-Za-z]+)", re.IGNORECASE)
PROMO_MONTHS_RE = re.compile(r"for the first\s+(\d+)\s+months|over\s+(\d+)\s+months", re.IGNORECASE)


def _parse_end_date(text: str, scraped_at: str) -> str | None:
    match = END_DATE_RE.search(text)
    if not match:
        return None
    day_str, month_name = match.groups()
    month_name = month_name.capitalize()
    if month_name not in MONTH_MAP:
        return None
    day = int(day_str)
    month = MONTH_MAP[month_name]
    scraped_dt = datetime.fromisoformat(scraped_at)
    candidate = datetime(scraped_dt.year, month, day)
    if candidate.date() < scraped_dt.date():
        candidate = candidate.replace(year=scraped_dt.year + 1)
    return candidate.date().isoformat()


def scrape() -> list[NbnPlan]:
    soup = fetch_static(URL)
    cards = soup.find_all("article", class_=lambda c: c and "product-card-nbnplans" in c)
    scraped_at = now_iso()
    plans: list[NbnPlan] = []
    seen_ids: set[str] = set()

    for card in cards:
        plan_id = card.get("data-nbn-id", "")
        if not plan_id or plan_id in seen_ids:
            continue
        seen_ids.add(plan_id)

        orig_price_str = card.get("data-plan-original-price", "0")
        regular_price = float(orig_price_str)
        if regular_price <= 0:
            continue

        dl_speed = card.get("data-plan-download-speed", "")
        ul_speed = card.get("data-plan-upload-speed", "")
        is_fibre = card.get("data-plan-is-fibre", "false").lower() == "true"

        text = card.get_text(" ", strip=True)

        nbn_name_match = re.search(r"NBN\s*(\d+)", text, re.IGNORECASE)
        plan_name = f"NBN {nbn_name_match.group(1)}" if nbn_name_match else f"NBN {dl_speed}"

        price_elem = card.find(class_=lambda cls: cls and "product-card-price" in cls) or card.find(
            class_=lambda cls: cls and "price" in cls.lower()
        )
        if price_elem:
            promo_price_val = parse_price(price_elem.get_text(strip=True))
        else:
            p_match = re.search(r"\$\s*(\d+)\s*/\s*month", text)
            promo_price_val = float(p_match.group(1)) if p_match else regular_price

        has_promo = promo_price_val < regular_price

        promo_months = None
        promo_end_date = None
        if has_promo:
            pm_match = PROMO_MONTHS_RE.search(text)
            promo_months = int(pm_match.group(1) or pm_match.group(2)) if pm_match else 6
            promo_end_date = _parse_end_date(text, scraped_at)
        else:
            promo_price_val = None

        tech_type = "Fibre" if is_fibre else "Fibre and FTTN"
        speed_tier = f"NBN {dl_speed}/{ul_speed}" if dl_speed and ul_speed else plan_name

        plans.append(
            NbnPlan(
                provider=PROVIDER,
                plan_name=plan_name,
                price_monthly=regular_price,
                promo_price=promo_price_val,
                promo_period_months=promo_months,
                promo_end_date=promo_end_date,
                contract_length="No lock-in contract",
                speed_tier=speed_tier,
                typical_evening_speed_mbps=float(dl_speed) if dl_speed else None,
                tech_type=tech_type,
                source_url=URL,
                scraped_at=scraped_at,
            )
        )

    return plans
