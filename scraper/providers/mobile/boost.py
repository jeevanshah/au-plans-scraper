"""Boost Mobile prepaid plans scraper. Static HTML.

Find plan cards via the 'productCard' CSS class. Each card contains
GB + price + expiry-period text within its subtree.
"""
import re
from datetime import datetime

from scraper.base import fetch_static
from scraper.schema import MobilePlan, now_iso

PROVIDER = "Boost Mobile"
URL = "https://www.boost.com.au/plans"
REQUIRES_JS = False

SALE_END_RE = re.compile(
    r"(?:[Ss]ale\s+ends\s+)(\d{1,2})\s+(January|February|March|April|May|June|"
    r"July|August|September|October|November|December)", re.I
)
GB_RE = re.compile(r"(\d+)\s*GB")
DOLLAR_RE = re.compile(r"\$\s*(\d+\.?\d*)")
# "28 DAY EXPIRY" / "186 DAY EXPIRY" / "365 DAY EXPIRY" / "6 MONTH (186 DAY) EXPIRY"
EXPIRY_RE = re.compile(r"(?:(\d+)\s+DAY\s+EXPIRY|(\d+)\s+MONTH\s*\(\s*(\d+)\s+DAY\s*\))", re.I)
WAS_RE = re.compile(r"was\s+\$(\d+)", re.I)
ONGOING_RE = re.compile(r"[Oo]ngoing\s+recharges?\s+\$(\d+)", re.I)
# "21GB for $28" / "160GB for $180"
FOR_PRICE_RE = re.compile(r"(\d+)\s*GB\s+for\s+\$\s*(\d+)", re.I)
# "THAT'S 26GB FOR $30 P/M" - paid upfront pricing hints
UPFRONT_RE = re.compile(r"PAID\s+UPFRONT", re.I)

MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}


def _parse_sale_end(text: str, scraped_at: str) -> str | None:
    m = SALE_END_RE.search(text)
    if not m:
        return None
    day_str, month_name = m.groups()
    day = int(day_str)
    month = MONTH_MAP[month_name.lower()]
    scraped_dt = datetime.fromisoformat(scraped_at)
    candidate = datetime(scraped_dt.year, month, day)
    if candidate.date() < scraped_dt.date():
        candidate = candidate.replace(year=scraped_dt.year + 1)
    return candidate.date().isoformat()


def scrape() -> list[MobilePlan]:
    soup = fetch_static(URL)
    scraped_at = now_iso()
    text = soup.get_text(" ", strip=True)

    promo_end_date = _parse_sale_end(text, scraped_at)
    plans: list[MobilePlan] = []
    seen: set[tuple[float, int]] = set()

    # Find plan cards by their productCard class
    for card in soup.find_all(class_=lambda c: c and "productCard" in c):
        txt = card.get_text(" ", strip=True)
        if len(txt) < 30:
            continue

        gb_match = GB_RE.search(txt)
        if not gb_match:
            continue
        gb = float(gb_match.group(1))
        if gb > 1000:
            continue

        # Extract expiry days from card text
        expiry_m = EXPIRY_RE.search(txt)
        if not expiry_m:
            continue

        if expiry_m.group(1):
            expiry_days = int(expiry_m.group(1))
        elif expiry_m.group(2) and expiry_m.group(3):
            # "6 MONTH (186 DAY)" format
            expiry_days = int(expiry_m.group(3))
        else:
            continue

        # Deduplicate by (GB, expiry_days) -- a card may appear multiple
        # times in the DOM across responsive breakpoints
        if (gb, expiry_days) in seen:
            continue

        # Extract prices from card text
        prices = DOLLAR_RE.findall(txt)
        if not prices:
            continue

        was_m = WAS_RE.search(txt)
        ongoing_m = ONGOING_RE.search(txt)
        for_price_m = FOR_PRICE_RE.search(txt)

        price_monthly: float | None = None
        promo_price: float | None = None

        if for_price_m:
            price_monthly = float(for_price_m.group(2))
            vals = sorted(set(float(p) for p in prices if float(p) > 1 and float(p) < price_monthly))
            if vals:
                promo_price = vals[0]
        elif was_m:
            price_monthly = float(was_m.group(1))
            vals = sorted(set(float(p) for p in prices if float(p) > 1 and float(p) < price_monthly))
            if vals:
                promo_price = vals[0]
        elif ongoing_m:
            price_monthly = float(ongoing_m.group(1))
            vals = sorted(set(float(p) for p in prices if float(p) > 1 and float(p) < price_monthly))
            if vals:
                promo_price = vals[0]
        else:
            vals = sorted(set(float(p) for p in prices if float(p) > 1))
            if vals:
                price_monthly = vals[0]

        if price_monthly is None or price_monthly <= 0:
            continue

        if expiry_days == 28:
            contract = "28-day expiry"
        elif expiry_days == 365:
            contract = "365-day expiry"
        elif expiry_days == 186:
            contract = "186-day expiry"
        else:
            contract = f"{expiry_days}-day expiry"

        seen.add((gb, expiry_days))

        plans.append(
            MobilePlan(
                provider=PROVIDER,
                plan_name=f"{gb:g}GB",
                price_monthly=price_monthly,
                promo_price=promo_price if promo_price and promo_price < price_monthly else None,
                promo_period_months=1 if (promo_price and promo_price < price_monthly) else None,
                promo_end_date=promo_end_date,
                contract_length=contract,
                billing_cycle_days=expiry_days,
                data_allowance_gb=gb,
                is_unlimited_data=False,
                network="Telstra",
                network_tech=None,
                source_url=URL,
                scraped_at=scraped_at,
            )
        )

    return plans