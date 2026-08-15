"""Dodo SIM-only mobile plans scraper. Static HTML.

Dodo mobile runs on the Optus network. Cards use 'plan-tile' class.
Promo tiles have "X% OFF FOR FIRST N MONTHS" banner; non-promo tiles have
single price. Offer end date in "Offer ends DD Mon YYYY" format.

Price extraction is scoped to the text between the GB figure and the
"/mth" unit label (PRICE_BLOCK_RE) -- tiles also mention unrelated dollar
amounts later on (e.g. "$200 international call credit", "$10/1GB daily
roaming") which a page-wide/tile-wide dollar search would also match.
Within that scoped block: the first amount is the "was" comparison price
(only present on promo tiles), and the amount immediately preceding "/mth"
is what's actually charged now -- anchored to that structural position,
not to numeric size, since the true relationship isn't "the smaller of two
numbers" but "whichever price is right before the /mth unit label."
"""
import re

from scraper.base import fetch_static
from scraper.schema import MobilePlan, now_iso

PROVIDER = "Dodo"
URL = "https://www.dodo.com/mobile"
REQUIRES_JS = False

GB_RE = re.compile(r"(\d+)\s*GB", re.I)
PRICE_BLOCK_RE = re.compile(r"\d+\s*GB\s+(.*?/mth)", re.I | re.S)
DOLLAR_RE = re.compile(r"\$\s*(\d+\.?\d*)")
PROMO_BANNER_RE = re.compile(r"(?:(\d+)%\s*OFF\s+FOR\s+FIRST\s+(\d+)\s+MONTHS)", re.I)
OFFER_ENDS_RE = re.compile(
    r"[Oo]ffer\s+ends\s+(\d{1,2})\s+(January|February|March|April|May|June|"
    r"July|August|September|October|November|December)\s*(\d{4})?", re.I
)

MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}


def _parse_offer_end(text):
    m = OFFER_ENDS_RE.search(text)
    if not m:
        return None
    day, month_name, year = m.groups()
    y = int(year) if year else 2026
    return "{}-{:02d}-{:02d}".format(y, MONTH_MAP[month_name.lower()], int(day))


def scrape():
    soup = fetch_static(URL)
    scraped_at = now_iso()
    text = soup.get_text(" ", strip=True)
    promo_end_date = _parse_offer_end(text)

    plans = []
    seen_gb = set()

    for tile in soup.find_all("div", class_="plan-tile"):
        txt = tile.get_text(" ", strip=True)
        if len(txt) < 40:
            continue

        gb_match = GB_RE.search(txt)
        if not gb_match:
            continue
        gb = float(gb_match.group(1))
        if gb < 1 or gb in seen_gb:
            continue

        # Detect promo banner: "50% OFF FOR FIRST 6 MONTHS"
        promo_banner = PROMO_BANNER_RE.search(txt)

        # Scope price extraction to the GB-figure...through..."/mth" window --
        # everything after "/mth" (call credits, roaming rates) is noise that
        # a tile-wide dollar search would otherwise also pick up.
        price_block_m = PRICE_BLOCK_RE.search(txt)
        if not price_block_m:
            continue
        prices = DOLLAR_RE.findall(price_block_m.group(1))
        vals = [float(p) for p in prices if float(p) > 1]
        if not vals:
            continue

        price_monthly = None
        promo_price = None
        promo_months = None

        if promo_banner:
            promo_pct, promo_months = int(promo_banner.group(1)), int(promo_banner.group(2))
            if len(vals) >= 2:
                # First amount in the scoped block is the "was" comparison
                # price; the one immediately preceding "/mth" (last in this
                # window) is what's actually charged now.
                price_monthly = vals[0]
                promo_price = vals[-1]
            else:
                price_monthly = vals[0]
                promo_price = vals[0] * (1 - promo_pct / 100)
        else:
            # No promo banner — single price
            price_monthly = vals[0]

        if price_monthly is None or price_monthly <= 1:
            continue

        if promo_price is not None and promo_price >= price_monthly:
            promo_price = None
            promo_months = None

        seen_gb.add(gb)
        plans.append(
            MobilePlan(
                provider=PROVIDER,
                plan_name="{}GB".format(int(gb)),
                price_monthly=price_monthly,
                promo_price=promo_price,
                promo_period_months=promo_months,
                promo_end_date=promo_end_date if promo_price else None,
                contract_length="Month-to-month",
                data_allowance_gb=gb,
                is_unlimited_data=False,
                network="Optus",
                network_tech=None,
                source_url=URL,
                scraped_at=scraped_at,
            )
        )

    return plans