"""Leaptel NBN plans scraper. JS-rendered -- needs fetch_js().

Leaptel's plans page (leaptel.com.au/plans/) is an Alpine.js-driven WordPress
block ("wp-block-leaptel-*"). A plain HTTP fetch (`fetch_static`) gets a
403 outright -- some bot-mitigation at the HTTP layer -- but a stock
Playwright browser context (bundled Chromium, no channel/UA override
needed, unlike Optus) passes fine.

The page actually renders every plan card TWICE in the DOM: a real,
complete "SSR preview" block (class `wp-block-leaptel-plan-list__ssr`,
explicitly commented in the page's own markup as "Server-rendered preview
using the real card markup/classes; hidden by Alpine once the interactive
list has real data") plus the live Alpine-interactive carousel that
replaces it. Both exist simultaneously and get_text() picks up both --
scoping to the SSR block specifically avoids double-counting/duplicate
extraction. Card class must be matched by EXACT token equality
(`c == "wp-block-leaptel-card"`), not substring -- a naive `"wp-block-
leaptel-card" in c` substring check also matches nested sub-elements like
`wp-block-leaptel-card__heading` (same gotcha as this project's Flip NBN
scraper's container-class matching).

Within each card: name is a plain heading, download/upload/typical-evening
speeds and the promo pricing ("$X / month $Y discount for N months, then
$Z ongoing") are all plain text on every card, and a per-card "Available
for <tech> technolog(y|ies) only" disclosure states the eligible NBN
connection tech where one is stated (fed into classify_tech_type()) --
absent entirely on the two plans (Pronto, Accelerated) available on every
fixed-line tech, matching this project's "return None rather than guessing
when no eligibility text is present" convention.
"""
import re

from scraper.base import classify_tech_type, fetch_js
from scraper.schema import NbnPlan, now_iso

PROVIDER = "Leaptel"
URL = "https://leaptel.com.au/plans/"
REQUIRES_JS = True

SPEED_RE = re.compile(r"(\d+)Mbps\s*DOWNLOAD\s*(\d+)Mbps\s*UPLOAD")
TYPICAL_RE = re.compile(r"Typical evening speed:\s*([\d.]+)\s*/\s*([\d.]+)\*?\s*Mbps")
PRICE_RE = re.compile(
    r"\$(\d+)\s*/\s*month\s*\$(\d+)\s*discount for (\d+)\s*months?,\s*then\s*\$([\d.]+)\s*ongoing"
)


def scrape() -> list[NbnPlan]:
    soup = fetch_js(URL, settle_ms=5000)
    scraped_at = now_iso()

    ssr = soup.find(class_=lambda c: c and c == "wp-block-leaptel-plan-list__ssr")
    if ssr is None:
        raise RuntimeError("scrape() could not find the wp-block-leaptel-plan-list__ssr block")

    cards = ssr.find_all("div", class_=lambda c: c and c == "wp-block-leaptel-card")

    plans = []
    for card in cards:
        name_el = card.find("h3", class_="wp-block-leaptel-card__heading__title")
        text = card.get_text(" ", strip=True)

        speed_m = SPEED_RE.search(text)
        typical_m = TYPICAL_RE.search(text)
        price_m = PRICE_RE.search(text)
        if not (name_el and speed_m and typical_m and price_m):
            continue

        down_mbps, up_mbps = speed_m.groups()
        typical_down, _typical_up = typical_m.groups()
        promo_price, _discount_amount, promo_months, regular_price = price_m.groups()

        plans.append(
            NbnPlan(
                provider=PROVIDER,
                plan_name=name_el.get_text(strip=True),
                price_monthly=float(regular_price),
                promo_price=float(promo_price),
                promo_period_months=int(promo_months),
                contract_length="No lock-in contract",
                speed_tier=f"NBN {down_mbps}/{up_mbps}",
                typical_evening_speed_mbps=float(typical_down),
                tech_type=classify_tech_type(text),
                source_url=URL,
                scraped_at=scraped_at,
            )
        )

    if not plans:
        raise RuntimeError("scrape() returned no plans")
    return plans
