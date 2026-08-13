"""Swoop NBN plans scraper. Static HTML, no JS/anti-bot -- straightforward.

Plan cards are `div.card--plan` -- semantic, well-labeled markup: the
regular price is genuinely marked `span.discount.strikethrough` and the
promo price `span.discount-price` (not a positional/numeric guess), the
nominal tier label lives in `.card__header .subheading` (e.g. "25/10
Mbps"), and typical evening download/upload speeds are the two `.h2`
figures in `.card__typical-speeds .speeds` (which can differ from the
nominal tier -- e.g. the "1000/100" tier's typical evening download is
890Mbps, not 1000).
"""
import re

from scraper.base import classify_tech_type, fetch_static
from scraper.schema import NbnPlan, now_iso

PROVIDER = "Swoop"
URL = "https://www.swoop.com.au/nbn/"
REQUIRES_JS = False

DURATION_RE = re.compile(r"off\s+for\s+(\d+)\s+months?", re.I)


def scrape() -> list[NbnPlan]:
    soup = fetch_static(URL)
    scraped_at = now_iso()

    cards = soup.find_all("div", class_=lambda c: c and "card--plan" in c)

    plans = []
    for card in cards:
        subheading = card.find(class_="subheading")
        regular_el = card.find("span", class_=lambda c: c and "strikethrough" in c)
        promo_el = card.find("span", class_="discount-price")
        speed_els = card.select(".card__typical-speeds .speeds .h2")
        if not (subheading and regular_el and promo_el and len(speed_els) == 2):
            continue

        tier_label = subheading.get_text(strip=True).replace("Mbps", "").strip()
        regular_price = float(regular_el.get_text(strip=True).lstrip("$"))
        promo_price = float(promo_el.get_text(strip=True).lstrip("$"))
        down_mbps = float(speed_els[0].get_text(strip=True))

        txt = card.get_text(" ", strip=True)
        duration_m = DURATION_RE.search(txt)
        promo_months = int(duration_m.group(1)) if duration_m else None

        plans.append(
            NbnPlan(
                provider=PROVIDER,
                plan_name=f"NBN {tier_label}",
                price_monthly=regular_price,
                promo_price=promo_price if promo_price < regular_price else None,
                promo_period_months=promo_months if promo_price < regular_price else None,
                contract_length="No lock-in contract",
                speed_tier=f"NBN {tier_label}",
                typical_evening_speed_mbps=down_mbps,
                tech_type=classify_tech_type(txt),
                source_url=URL,
                scraped_at=scraped_at,
            )
        )

    if not plans:
        raise RuntimeError("scrape() returned no plans")
    return plans
