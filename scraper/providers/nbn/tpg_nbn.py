"""TPG NBN plans scraper. Static HTML (AngularJS, server-rendered but
unresolved -- see below).

TPG's NBN page is a legacy AngularJS app: the raw HTML is un-rendered
template source (`{* ... *}` expressions), because final pricing depends on
JS evaluation *and* a real address being entered for eligibility/tech-type
detection. However, the literal price values for both branches of each
promo ternary are embedded directly in the template source as string
arguments, e.g.:

    {* promotion.hasSixMonthPromotion('TPG_FTTN_Bundle_Homefast_SL_201711')
       ? getDollars('69.99') : getDollars('94.99') *}

-- so the real promo/regular prices can be read straight out of the raw
template text without needing a browser or an address, by matching the
`getDollars('X') : getDollars('Y')` pattern per plan card. (A plain "$X/mth"
text search does NOT work here -- there's no literal number between "$" and
"/mth" in the raw source, just this unresolved template expression.)

Each named tier (e.g. "NBN100") repeats once per possible connection
technology (FTTN, FTTC, Fibre, FTTB, HFC, Wireless) as an ng-show-gated
`.planCards` div -- only one is shown at a time based on the address's real
tech type, but a static fetch renders all of them. This scraper dedupes by
tier name, keeping the first-seen (FTTN) variant, the same "pick one
consistent variant" approach this project's Telstra NBN scraper uses for
its own hidden-variant duplicates. Different tech variants can carry
different promo SKU pricing for the "same" advertised tier -- FTTN is kept
as the representative default since it's the most common TPG connection
type.

Non-NBN alternative products (5G Plus/Premium, "FTTB Max"/FTTB25/FTTB100
wireless-branded plans, Home Wireless Broadband) are excluded by requiring
the card's ng-show promo SKU to contain "_Bundle_" -- the real signal this
page itself uses to distinguish genuine NBN bundle plans from wireless
alternatives (which don't use that SKU-naming convention), rather than
guessing from the display name alone.
"""
import re

from scraper.base import classify_tech_type, fetch_static, normalize_nbn_speed_tier
from scraper.schema import NbnPlan, now_iso

PROVIDER = "TPG"
URL = "https://www.tpg.com.au/nbn"
REQUIRES_JS = False

DOLLAR_TERNARY_RE = re.compile(r"getDollars\('([\d.]*)'\)\s*:\s*getDollars\('([\d.]*)'\)")
DURATION_RE = re.compile(r"for\s+(\d+)\s+months?", re.I)
TECH_RE = re.compile(r"'(\w+)'\s*===\s*selectedPlan\.tech")


def scrape() -> list[NbnPlan]:
    soup = fetch_static(URL)
    scraped_at = now_iso()

    cards = soup.find_all("div", class_=lambda c: c and "planCards" in c)

    plans = []
    seen_tiers = set()

    for card in cards:
        name_el = card.find("h3", class_="name")
        if not name_el:
            continue
        tier_name = name_el.get_text(strip=True)
        if tier_name in seen_tiers:
            continue

        ng_show = card.get("ng-show") or ""
        if "_Bundle_" not in ng_show:
            continue  # wireless-alternative product, not a real NBN plan

        ternary_m = DOLLAR_TERNARY_RE.search(str(card))
        if not ternary_m:
            continue
        promo_str, regular_str = ternary_m.groups()
        if not regular_str:
            continue
        regular_price = float(regular_str)
        promo_price = float(promo_str) if promo_str else None
        if promo_price is not None and promo_price >= regular_price:
            promo_price = None

        txt = card.get_text(" ", strip=True)
        duration_m = DURATION_RE.search(txt)
        promo_months = int(duration_m.group(1)) if (duration_m and promo_price) else None

        down_el = card.find("div", class_="download-speed")
        up_el = card.find("div", class_="upload-speed")
        down_m = re.search(r"\d+", down_el.get_text()) if down_el else None
        up_m = re.search(r"\d+", up_el.get_text()) if up_el else None
        if not (down_m and up_m):
            continue
        down_mbps, up_mbps = int(down_m.group()), int(up_m.group())

        tech_m = TECH_RE.search(ng_show)
        tech_type = classify_tech_type(tech_m.group(1)) if tech_m else None

        tier, _, _ = normalize_nbn_speed_tier(down_mbps, up_mbps)
        seen_tiers.add(tier_name)
        plans.append(
            NbnPlan(
                provider=PROVIDER,
                plan_name=tier_name,
                price_monthly=regular_price,
                promo_price=promo_price,
                promo_period_months=promo_months,
                contract_length="No lock-in contract",
                speed_tier=tier,
                typical_evening_speed_mbps=float(down_mbps),
                tech_type=tech_type,
                source_url=URL,
                scraped_at=scraped_at,
            )
        )

    if not plans:
        raise RuntimeError("scrape() returned no plans")
    return plans
