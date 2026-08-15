"""amaysim SIM-only mobile plans scraper. Static AEM-rendered HTML, no JS needed.

amaysim runs on the Optus network. The /sim-plans page groups plans into
four categories (28-day, long-expiry, data-only, 7-day) and renders them as
<article class="product-card product-card-plan ..."> cards with data-* attributes.

Duplicate cards (same data-plan-id appearing in multiple group sections) are
deduplicated by plan ID.
"""
import re

from scraper.base import fetch_static
from scraper.schema import MobilePlan, now_iso

PROVIDER = "amaysim"
URL = "https://www.amaysim.com.au/sim-plans"
REQUIRES_JS = False

# "Ongoing is $320 for 240GB/365 days. Ends 20th July."
# Handles ordinal date suffixes ("30th", "20th") that base.py's
# parse_relative_end_date (which expects "30 July") can't match.
TERMS_RE = re.compile(
    r"Ongoing is \$(\d+) for (\d+)GB/(\d+) days\.\s+Ends (\d+)\w+\s+(\w+)"
)
# "$ 12 Save $23 first renewal"
PROMO_PRICE_RE = re.compile(r"\$\s*(\d+)\s+Save")
# "28 day renewal" / "365 day renewal" via product-card-renewal CSS class
RENEWAL_RE = re.compile(r"(\d+)\s+day\s+renewal")
# "Mobile plan includes 5G" / "4G" 
NETWORK_TECH_RE = re.compile(r"Mobile plan includes\s+(5G|4G)")

MONTH_MAP = {
    "January": 1, "February": 2, "March": 3, "April": 4,
    "May": 5, "June": 6, "July": 7, "August": 8,
    "September": 9, "October": 10, "November": 11, "December": 12,
}


def _parse_terms_end_date(text: str, scraped_at: str) -> str | None:
    """Extract promo end-date from terms text like 'Ends 30th July'.

    Returns ISO date string or None. Rolls forward a year if the date
    has already passed relative to scraped_at, matching the semantics
    of base.parse_relative_end_date.
    """
    from datetime import datetime

    match = TERMS_RE.search(text)
    if not match:
        return None

    _ongoing_price, _gb, _days, day_str, month_name = match.groups()
    if month_name not in MONTH_MAP:
        return None

    day = int(day_str)
    month = MONTH_MAP[month_name]
    scraped_dt = datetime.fromisoformat(scraped_at)
    candidate = datetime(scraped_dt.year, month, day)
    if candidate.date() < scraped_dt.date():
        candidate = candidate.replace(year=scraped_dt.year + 1)
    return candidate.date().isoformat()


def scrape() -> list[MobilePlan]:
    soup = fetch_static(URL)
    cards = soup.find_all(
        "article", class_=lambda c: c and "product-card-plan" in c
    )
    scraped_at = now_iso()

    seen_ids: set[str] = set()
    plans: list[MobilePlan] = []

    for card in cards:
        plan_id = card.get("data-plan-id", "")
        if not plan_id:
            continue
        if plan_id in seen_ids:
            continue
        seen_ids.add(plan_id)

        text = card.get_text(" ", strip=True)
        has_promo = "plan-hasflag-true" in " ".join(card.get("class", []))

        base_price = float(card.get("data-base-price", "0"))
        base_data = float(card.get("data-base-data", "0"))

        # Regular price comes from the terms regex for promo plans,
        # or from data-base-price for non-promo plans.
        terms_match = TERMS_RE.search(text)
        price_monthly: float
        promo_price: float | None = None
        promo_end_date: str | None = None

        if has_promo and terms_match:
            # The ongoing price from the terms text is the regular price.
            ongoing_price = float(terms_match.group(1))
            price_monthly = ongoing_price
            promo_match = PROMO_PRICE_RE.search(text)
            if promo_match:
                promo_price = float(promo_match.group(1))
                # Only set an end-date when there's an actual discount to
                # attach it to -- the "Ends <date>" terms text can appear
                # (a signup-window deadline) even on cards where the "Save
                # $X" sub-badge isn't present, i.e. no real promo_price.
                # Leaving promo_end_date set in that case would let a flat,
                # non-discounted plan carry a real validUntil date
                # downstream (transform.py passes it through unconditionally).
                promo_end_date = _parse_terms_end_date(text, scraped_at)
        else:
            price_monthly = base_price
            promo_price = None
            promo_end_date = None

        if price_monthly <= 0:
            continue

        # Plan name: use data-base-data + the group heading context,
        # but the simplest sane name is "{data}GB" since amaysim
        # doesn't have distinctive tier names.
        plan_name = f"{base_data:g}GB"

        # Renewal period from product-card-renewal element
        renewal_match = RENEWAL_RE.search(text)
        renewal_days = int(renewal_match.group(1)) if renewal_match else 28

        if renewal_days == 7:
            contract_length = "7-day expiry"
        elif renewal_days == 28:
            contract_length = "28-day expiry"
        elif renewal_days == 365:
            contract_length = "365-day expiry"
        else:
            contract_length = f"{renewal_days}-day expiry"

        # Network tech (5G/4G)
        tech_match = NETWORK_TECH_RE.search(text)

        plans.append(
            MobilePlan(
                provider=PROVIDER,
                plan_name=plan_name,
                price_monthly=price_monthly,
                promo_price=promo_price,
                promo_period_months=1 if promo_price is not None else None,
                promo_end_date=promo_end_date,
                contract_length=contract_length,
                data_allowance_gb=base_data,
                is_unlimited_data=False,
                network="Optus",
                network_tech=tech_match.group(1) if tech_match else None,
                source_url=URL,
                scraped_at=scraped_at,
            )
        )

    return plans