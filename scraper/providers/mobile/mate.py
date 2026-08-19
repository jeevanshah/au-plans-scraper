"""MATE (Mate Communicate) mobile plans scraper. Static HTML, no JS needed.

Real domain is letsbemates.com.au (NOT matecommunicate.com.au, which
redirects/rebrands to this site) -- plans page is
https://www.letsbemates.com.au/mobile/. MATE resells the Telstra Wholesale
Mobile Network, SIM-only, no lock-in contract (one-month minimum term).

The page's initial "MOBILE PLANS" tab (5G, standard data-only-excluded)
renders 4 real plan cards server-side as
<div data-connection="5g" data-plan-type="standard"> -- a precise, exact
data-attribute match. The "4G Mobile Plans" tab and "DATA ONLY PLANS" filter
are JS-driven (data-connection="${type}" template-literal placeholders exist
in a client-side script) and are NOT present in the static HTML at all, so
there's no risk of them being picked up by a class-substring scan.

Each card advertises a "double/quadruple data for 6 months" bonus-data
promo (e.g. Good Mates: 15GB every month, temporarily 60GB for the first 6
months) rather than a price discount -- the $/month price itself doesn't
change. MobilePlan's promo_price/promo_period_months/promo_end_date fields
exist specifically for *price* discounts (see amaysim's scraper and
NOTES.md for the bug where promo_end_date got set without a real price
promo), so this scraper deliberately leaves them unset and reports only the
steady-state (post-promo) data allowance from the struck-through GB figure
-- inventing a promo_price here would misrepresent a data bonus as a price
cut.

GB allowance: the pill badge in .speed-box contains a
<span class="text-decoration-line-through"> holding the real ongoing GB
figure, followed by the temporary bonus GB text (e.g. "15GB" struck through,
then "60GB Data*"). Price is the $ span inside .plan-type p (class
"text-green fw-bold").
"""
import re

from scraper.base import fetch_static, parse_price
from scraper.schema import MobilePlan, now_iso

PROVIDER = "Mate"
URL = "https://www.letsbemates.com.au/mobile/"
REQUIRES_JS = False

GB_RE = re.compile(r"(\d+(?:\.\d+)?)\s*GB", re.I)


def scrape() -> list[MobilePlan]:
    soup = fetch_static(URL)
    scraped_at = now_iso()

    cards = soup.find_all("div", attrs={"data-connection": "5g", "data-plan-type": "standard"})

    plans: list[MobilePlan] = []
    for card in cards:
        name_el = card.find("h3")
        speed_box = card.find(class_="speed-box")
        plan_type_el = card.find(class_="plan-type")
        if not (name_el and speed_box and plan_type_el):
            continue

        plan_name = name_el.get_text(strip=True)

        # Steady-state (non-promotional) GB is the struck-through figure when
        # a bonus-data promo is running; otherwise it's the only GB figure present.
        strike = speed_box.find(class_="text-decoration-line-through")
        gb_source = strike.get_text(" ", strip=True) if strike else speed_box.get_text(" ", strip=True)
        gb_match = GB_RE.search(gb_source)
        if not gb_match:
            continue
        data_gb = float(gb_match.group(1))

        price_span = plan_type_el.find("span")
        if not price_span:
            continue
        try:
            price_monthly = parse_price(price_span.get_text())
        except ValueError:
            continue
        if price_monthly <= 0:
            continue

        plans.append(
            MobilePlan(
                provider=PROVIDER,
                plan_name=plan_name,
                price_monthly=price_monthly,
                promo_price=None,
                promo_period_months=None,
                promo_end_date=None,
                contract_length="Month-to-month",
                data_allowance_gb=data_gb,
                is_unlimited_data=False,
                network="Telstra",
                network_tech="5G",
                source_url=URL,
                scraped_at=scraped_at,
            )
        )

    if not plans:
        raise RuntimeError("scrape() found the plans page but no valid plan cards")

    return plans
