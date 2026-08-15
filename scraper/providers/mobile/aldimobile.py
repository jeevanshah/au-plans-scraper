"""ALDImobile SIM-only plans scraper. Static HTML.

Includes Mobile 30-day tiers, Long Life 365-day plan. Skips Family (multi-service
bundles) and data-only 365-day plans (out of scope for MobilePlan schema).

"Price Promise" text locks pricing until a stated date -- extracted as
promo_end_date when present.
"""
import re
from datetime import datetime

from scraper.base import fetch_static
from scraper.schema import MobilePlan, now_iso

PROVIDER = "ALDImobile"
URL = "https://www.aldimobile.com.au/plans/"
REQUIRES_JS = False

# "Price Promise until 31/12/2026" / "Price Promise until 31 December 2026"
PRICE_PROMISE_RE = re.compile(
    r"Price\s+Promise\s+(?:valid\s+)?until\s+"
    r"(\d{1,2})[/\s]+(\d{1,2}|January|February|March|April|May|June|July|"
    r"August|September|October|November|December)[/\s]+(\d{4})",
    re.I,
)
# Pricing: "$XX" in h4
DOLLAR_RE = re.compile(r"[$]\s*(\d+\.?\d*)")
# "XX GB" data
GB_RE = re.compile(r"(\d+)\s*GB", re.I)
# "30 Day" / "365 Day" / "Long Life"
EXPIRY_30_RE = re.compile(r"30\s*[Dd]ay", re.I)
EXPIRY_365_RE = re.compile(r"365\s*[Dd]ay|Long\s*Life", re.I)
# Family / data-only exclusion
FAMILY_RE = re.compile(r"[Ff]amily", re.I)
DATA_ONLY_RE = re.compile(r"[Dd]ata\s*[Oo]nly", re.I)

MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}


def _parse_price_promise(text: str) -> str | None:
    """Extract 'Price Promise until DD/MM/YYYY' or similar."""
    match = PRICE_PROMISE_RE.search(text)
    if not match:
        return None
    day_or_first, month_or_second, year = match.groups()
    try:
        day = int(day_or_first)
        if month_or_second.isdigit():
            month = int(month_or_second)
        else:
            month = MONTH_MAP[month_or_second.lower()]
        year_i = int(year)
        return f"{year_i}-{month:02d}-{day:02d}"
    except (ValueError, KeyError):
        return None


def scrape() -> list[MobilePlan]:
    soup = fetch_static(URL)
    scraped_at = now_iso()
    text = soup.get_text(" ", strip=True)

    promo_end_date = _parse_price_promise(text)

    plans: list[MobilePlan] = []
    seen: set[float] = set()

    # ALDI renders plan cards in a grid. Find card blocks by looking for
    # elements containing both "$" and "GB" and "Day" in close proximity.
    for tag in soup.find_all(["div", "section", "article"]):
        txt = tag.get_text(" ", strip=True)
        if len(txt) < 30 or len(txt) > 500:
            continue
        if "$" not in txt or "GB" not in txt:
            continue

        # Skip Family and Data Only
        if FAMILY_RE.search(txt) or DATA_ONLY_RE.search(txt):
            continue

        # Extract GB
        gb_match = GB_RE.search(txt)
        if not gb_match:
            continue
        gb = float(gb_match.group(1))

        if gb in seen:
            continue

        # Extract price
        prices = DOLLAR_RE.findall(txt)
        if not prices:
            continue
        price_monthly = float(prices[0])

        # Determine contract length
        if EXPIRY_365_RE.search(txt):
            contract = "365-day expiry"
            billing_cycle_days = 365
        elif EXPIRY_30_RE.search(txt):
            contract = "30-day expiry"
            billing_cycle_days = 30
        else:
            continue  # Unknown expiry period, skip

        if price_monthly <= 0:
            continue

        seen.add(gb)

        plans.append(
            MobilePlan(
                provider=PROVIDER,
                plan_name=f"{gb:g}GB",
                price_monthly=price_monthly,
                promo_price=None,
                promo_period_months=None,
                promo_end_date=promo_end_date,
                contract_length=contract,
                billing_cycle_days=billing_cycle_days,
                data_allowance_gb=gb,
                is_unlimited_data=False,
                network="Telstra",  # ALDImobile runs on Telstra wholesale
                network_tech=None,
                source_url=URL,
                scraped_at=scraped_at,
            )
        )

    return plans