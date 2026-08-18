"""Kogan Internet (nbn) plans scraper. Static HTML, no JS rendering needed.

The live plans page is https://www.koganinternet.com.au/plans/ -- note this
is NOT /nbn/ (that path 404s). Unlike most providers here, none of the six
NBN speed-tier cards' data lives in visible rendered text/CSS classes at all:
the whole page is a page-builder shell and every card's title, pricing, tier,
and eligibility text is embedded as a JSON blob assigned via
`window.bootstrapPlans['<uuid>'] = JSON.parse('...')` inside an inline
<script> tag next to each card's placeholder div. The JSON.parse() argument
is a JS single-quoted string with every double-quote, hyphen, and non-ASCII
character (nbsp, (R), arrows) \\u-escaped -- decode by replacing all \\uXXXX
sequences with their character before handing the result to json.loads().

The page also renders one unrelated "4G Internet" (fixed-wireless, 90-day
plan) card via the exact same bootstrapPlans mechanism -- it's excluded by
checking speedTier/title, since it's a different product line, not an NBN
speed tier.

Each plan's advertised nbn(R) speed tier (e.g. "nbn(R) 25", "nbn(R) 500") is
only present as an <h3> inside the `speedDisclaimer` HTML fragment, not as a
top-level field -- `downstreamBandwidth`/`upstreamBandwidth` in the JSON are
actually the *typical evening speed* figures (confirmed against the
"Typical evening speeds: ~X Mbps & Y Mbps" text alongside them, which matches
those two fields exactly for every tier, e.g. Gold advertises tier "100" but
downstreamBandwidth is 98).

`rate` is the discounted price charged for the first 12 months; `rateRrp`
(and the "$X/month thereafter" text in `pricingInfo`) is the true ongoing
price after the promo ends. `isPromo`/`promoText` confirm every NBN tier here
runs the same "for first 12 months" promo -- there's no non-promo tier.

Tech-type eligibility text (`eligibilityDisclaimer`) is only non-empty for
the FTTB/N/C-only and FTTP/HFC-only tiers (Gold through Diamond); Bronze and
Silver have no disclosed eligibility restriction, so tech_type is left
unset for those per the "never guess" convention.
"""
import json
import re

from scraper.base import classify_tech_type, fetch_static
from scraper.schema import NbnPlan, now_iso

PROVIDER = "Kogan Internet"
URL = "https://www.koganinternet.com.au/plans/"
REQUIRES_JS = False

BOOTSTRAP_RE = re.compile(r"window\.bootstrapPlans\['[^']+'\]\s*=\s*JSON\.parse\('(.*?)'\);", re.S)
UNICODE_ESCAPE_RE = re.compile(r"\\u([0-9a-fA-F]{4})")
TIER_RE = re.compile(r"<h3[^>]*>[^<]*?(\d[\d.]*)\s*</h3>")
THEREAFTER_RE = re.compile(r"\$([\d.]+)/month thereafter")


def _decode(js_string_literal: str) -> dict:
    return json.loads(UNICODE_ESCAPE_RE.sub(lambda m: chr(int(m.group(1), 16)), js_string_literal))


def scrape() -> list[NbnPlan]:
    soup = fetch_static(URL)
    scraped_at = now_iso()
    plans: list[NbnPlan] = []

    for raw in BOOTSTRAP_RE.findall(str(soup)):
        plan = _decode(raw)
        title = plan.get("title", "")
        speed_disclaimer = plan.get("speedDisclaimer", "")
        tier_match = TIER_RE.search(speed_disclaimer)
        # Skip the unrelated "4G Internet" fixed-wireless card -- it has no
        # nbn(R) speed-tier <h3> in its speedDisclaimer at all.
        if not tier_match:
            continue

        thereafter_match = THEREAFTER_RE.search(plan.get("pricingInfo", ""))
        if not thereafter_match:
            continue

        promo_price = float(plan["rate"])
        price_monthly = float(thereafter_match.group(1))
        eligibility_text = re.sub("<[^>]+>", " ", plan.get("eligibilityDisclaimer", ""))

        plans.append(
            NbnPlan(
                provider=PROVIDER,
                plan_name=f"{title} NBN {tier_match.group(1)}",
                price_monthly=price_monthly,
                promo_price=promo_price if promo_price < price_monthly else None,
                promo_period_months=12 if plan.get("isPromo") and promo_price < price_monthly else None,
                contract_length="No lock-in contract",
                speed_tier=f"NBN {tier_match.group(1)}",
                typical_evening_speed_mbps=float(plan["downstreamBandwidth"]),
                tech_type=classify_tech_type(eligibility_text),
                source_url=URL,
                scraped_at=scraped_at,
            )
        )

    if not plans:
        raise RuntimeError("scrape() could not parse any plans from the Kogan Internet plans page")
    return plans
