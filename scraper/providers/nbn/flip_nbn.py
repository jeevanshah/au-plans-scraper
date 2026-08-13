"""Flip NBN plans scraper. JS-rendered SPA (Vue/Vuetify) -- needs fetch_js().

The real plans page is https://flipconnect.com.au/cheap-nbn-plans (NOT the
bare homepage, which only has a "from $48/month" teaser with no per-tier
data -- that mismatch is what caused earlier attempts to come back empty).

Plan cards are the direct children of a `plans-*-inner` container (each
wrapped in a `.flex-shrink-0` div) -- a precise, real DOM anchor, not a
page-wide scan of every div/section/article by text length. The container's
exact class has already changed once (`plans-scroll-inner` -> `plans-wrap-
inner`, when Flip redesigned this section from a horizontal-scroll carousel
to a wrapping grid) -- matched via a `plans-\w+-inner` pattern instead of an
exact string so a similar future rename doesn't silently break this again.
Within each card: `.text-flipRed` holds the marketing tier name (e.g.
"Premium"), `.text-price` holds the promo price, and the regular/ongoing
price plus promo duration are read from the card's own "For 6 months, then
$65.90 ongoing*" text -- not guessed from number size.
"""
import re

from scraper.base import classify_tech_type, fetch_js
from scraper.schema import NbnPlan, now_iso

PROVIDER = "Flip"
URL = "https://flipconnect.com.au/cheap-nbn-plans"
REQUIRES_JS = True

ONGOING_RE = re.compile(r"then\s*\$([\d.]+)\s*ongoing", re.I)
DURATION_RE = re.compile(r"[Ff]or\s+(\d+)\s*months", re.I)
SPEED_RE = re.compile(r"(\d+)\s*Mbps\s*Download.*?(\d+)\s*Mbps\s*Upload", re.I | re.S)
PLANS_INNER_RE = re.compile(r"plans-\w+-inner")


def scrape() -> list[NbnPlan]:
    soup = fetch_js(URL, settle_ms=6000)
    scraped_at = now_iso()

    scroll = soup.find(class_=lambda c: c and PLANS_INNER_RE.search(c))
    if scroll is None:
        raise RuntimeError("scrape() could not find the plans-*-inner container")

    cards = scroll.find_all("div", class_=lambda c: c and "flex-shrink-0" in c, recursive=False)

    plans = []
    for card in cards:
        name_el = card.find(class_=lambda c: c and "text-flipRed" in c)
        price_el = card.find(class_=lambda c: c and "text-price" in c)
        if not (name_el and price_el):
            continue

        txt = card.get_text(" ", strip=True)
        ongoing_m = ONGOING_RE.search(txt)
        speed_m = SPEED_RE.search(txt)
        if not (ongoing_m and speed_m):
            continue

        promo_price = float(price_el.get_text(strip=True))
        regular_price = float(ongoing_m.group(1))
        duration_m = DURATION_RE.search(txt)
        promo_months = int(duration_m.group(1)) if duration_m else None

        down_mbps, up_mbps = speed_m.groups()

        plans.append(
            NbnPlan(
                provider=PROVIDER,
                plan_name=name_el.get_text(strip=True),
                price_monthly=regular_price,
                promo_price=promo_price if promo_price < regular_price else None,
                promo_period_months=promo_months if promo_price < regular_price else None,
                contract_length="No lock-in contract",
                speed_tier=f"NBN {down_mbps}/{up_mbps}",
                typical_evening_speed_mbps=float(down_mbps),
                tech_type=classify_tech_type(txt),
                source_url=URL,
                scraped_at=scraped_at,
            )
        )

    if not plans:
        raise RuntimeError("scrape() returned no plans")
    return plans
