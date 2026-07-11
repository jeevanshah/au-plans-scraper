"""Kogan Mobile prepaid plans scraper. Static HTML (WordPress/Elementor).

Monthly plans (15GB-80GB) and 365-Day plans (140GB-500GB). Member/non-member
dual pricing extracted from card-level HTML. Promo end-date in "11:59PM AEST
DD/MM/YYYY" format.

365-day cards contain an annualized cost-average blurb like
"That's only $13.25 per month" — these are NOT promo prices, they're just
marketing copy showing (upfront_price / 12). Exclude them from promo detection.

Deduplication keys on (GB, price_monthly) — two cars with the same data
allowance AND the same regular price are the same plan tier regardless of
what contract text happens to be visible in the card. This handles both
true duplicates (same card repeated across responsive sections) and the
case where Kogan's "Hot deals" section repeats the same 365-day plans that
also appear in the regular "365 days" section below.
"""
import re

from scraper.base import fetch_static
from scraper.schema import MobilePlan, now_iso

PROVIDER = "Kogan Mobile"
URL = "https://www.koganmobile.com.au/plans"
REQUIRES_JS = False

END_DATE_RE = re.compile(r"11:59\s?[AP]M\s?AE[SD]T\s+(\d{1,2})/(\d{1,2})/(\d{4})")
GB_RE = re.compile(r"(\d+)\s*GB")
DOLLAR_RE = re.compile(r"\$\s*(\d+\.?\d*)")
YEARLY_RE = re.compile(r"365\s*[Dd]ay")

# Genuine promo-price markers — all live inside the card div itself
NON_MEMBER_RE = re.compile(r"[Nn]on[- ]?[Mm]ember\s*[Pp]rice:\s*\$\s*(\d+\.?\d*)")
WAS_RE = re.compile(r"[Ww]as\s+\$\s*(\d+\.?\d*)")
FIRST_MONTH_RE = re.compile(r"\$\s*(\d+\.?\d*)\s*[Ff]or\s+(?:the\s+)?first\s+month", re.I)
THEREAFTER_RE = re.compile(r"\$\s*(\d+\.?\d*)\s*thereafter", re.I)

# Annualized cost-average marketing copy — NOT a promo price
THATSONLY_RE = re.compile(r"[Tt]hat'?s\s+only\s+\$\s*(\d+\.?\d*)\s*(?:per\s+month)?", re.I)


def _parse_end_date(text: str) -> str | None:
    m = END_DATE_RE.search(text)
    if not m:
        return None
    day, month, year = m.groups()
    return f"{year}-{month.zfill(2)}-{day.zfill(2)}"


def _real_prices(prices: list[str], ctx: str) -> list[float]:
    """Return numeric prices that are NOT annualized marketing blurbs."""
    thatsonly_vals: set[float] = set()
    for m in THATSONLY_RE.finditer(ctx):
        thatsonly_vals.add(float(m.group(1)))
    return [
        float(p) for p in prices
        if float(p) not in thatsonly_vals and float(p) > 1
    ]


def scrape() -> list[MobilePlan]:
    soup = fetch_static(URL)
    scraped_at = now_iso()
    promo_end_date = _parse_end_date(soup.get_text(" ", strip=True))

    plans: list[MobilePlan] = []
    # Dedup key: (GB, price_monthly). Two cards with the same GB AND the same
    # regular price are the same plan tier — more robust than (GB, contract)
    # when contract-detection text lives in section headings outside the card.
    seen: set[tuple[float, float]] = set()

    # Find plan cards via rounded shadow card divs
    for card in soup.find_all(
        class_=lambda c: c and "tw-rounded-md" in c and "tw-bg-white" in c and "tw-shadow" in c
    ):
        txt = card.get_text(" ", strip=True)
        if len(txt) < 25:
            continue

        gb_match = GB_RE.search(txt)
        if not gb_match:
            continue
        gb = float(gb_match.group(1))
        if gb < 10:
            continue

        # All promo markers ("Was $X", "Non-Member Price:", "365 Day",
        # "first month", "That's only") live inside the card div itself
        # in Kogan's markup — scope to the card element only, no parent
        # text that could leak from sibling cards.
        ctx = txt
        is_yearly = bool(YEARLY_RE.search(ctx))
        contract = "365-day expiry" if is_yearly else "Month-to-month"

        prices = DOLLAR_RE.findall(ctx)
        if not prices:
            continue

        non_member_m = NON_MEMBER_RE.search(ctx)
        was_m = WAS_RE.search(ctx)
        first_m = FIRST_MONTH_RE.search(ctx)
        thereafter_m = THEREAFTER_RE.search(ctx)

        price_monthly: float | None = None
        promo_price: float | None = None

        if non_member_m:
            price_monthly = float(non_member_m.group(1))
            real = _real_prices(prices, ctx)
            for p in sorted(set(real), reverse=True):
                if p < price_monthly:
                    promo_price = p
                    break
        elif was_m:
            price_monthly = float(was_m.group(1))
            real = _real_prices(prices, ctx)
            for p in sorted(set(real)):
                if p < price_monthly:
                    promo_price = p
                    break
        elif thereafter_m and first_m:
            price_monthly = float(thereafter_m.group(1))
            promo_price = float(first_m.group(1))
        else:
            real = sorted(set(_real_prices(prices, ctx)))
            if len(real) >= 2:
                promo_price = real[0]
                price_monthly = real[1]
            elif real:
                price_monthly = real[0]

        if price_monthly is None or price_monthly <= 0:
            continue

        if promo_price is not None and promo_price >= price_monthly:
            promo_price = None

        # Deduplicate by (GB, regular price).  Two cards with identical GB
        # and identical regular price are the same plan tier — even if one
        # happens to have "365 Day" inline and the other gets it from a
        # parent section heading (the fixture repeats plans across "Hot
        # deals" + regular "365 days" sections and the duplicate card in
        # the regular section may not have "365 Day" in its own text).
        key = (gb, price_monthly)
        if key in seen:
            continue
        seen.add(key)

        plans.append(
            MobilePlan(
                provider=PROVIDER,
                plan_name=f"{gb:g}GB",
                price_monthly=price_monthly,
                promo_price=promo_price,
                promo_period_months=1 if promo_price is not None else None,
                promo_end_date=promo_end_date,
                contract_length=contract,
                data_allowance_gb=gb,
                is_unlimited_data=False,
                network="Vodafone",
                network_tech=None,
                source_url=URL,
                scraped_at=scraped_at,
            )
        )

    return plans