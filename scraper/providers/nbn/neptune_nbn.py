"""Neptune Internet NBN plans scraper. JS-rendered -- needs fetch_js().

Neptune's main plans page (/internet) is address-gated -- it shows no
pricing at all until a real connection address is entered, so it can't be
scraped generically. Instead this scrapes the Critical Information Summary
page (/critical-information-summary), a single combined pricing table
covering every plan Neptune offers -- a regulatory disclosure required of
all Australian telcos, so it's guaranteed to be complete and address-
independent.

The page itself IS behind Cloudflare bot-management (403 with Cf-Mitigated/
CF-RAY headers via a plain HTTP client or WebFetch), but a real Playwright
browser context passes with no stealth patches needed -- Neptune's
Cloudflare rule appears to check for genuine browser/JS capability, not a
harder fingerprint/proxy check.

The table has no separate section-header rows for "Standard Plans" /
"Fixed Wireless Plans" / "FTTP Only Plans" / "Business Plans" (those are
page headings outside the table, not part of its <tr> structure) -- most
rows self-identify via a "(Fixed Wireless)" or "(FTTP)" suffix on the plan
name, or "eSLA" for business-tier plans, but one FTTP-tier row lacks any
suffix at all. Rather than relying on a fixed row count/position (fragile
if Neptune adds or removes a tier), this tracks section membership as a
state machine over row order: once a "(Fixed Wireless)" row is seen we're
in that section; the next unmarked row after leaving it is the (unlabeled)
first FTTP-only row; "eSLA" rows are Business. Only Standard and FTTP-only
residential plans are kept -- Fixed Wireless (not fixed-line NBN, same
convention as this project's other providers excluding it) and Business
(requires an ABN) are excluded.
"""
import re

from scraper.base import classify_tech_type, fetch_js
from scraper.schema import NbnPlan, now_iso

PROVIDER = "Neptune Internet"
URL = "https://www.neptune.net.au/critical-information-summary"
REQUIRES_JS = True

PLAN_RE = re.compile(r"(\d+)mbps\s*Download\s*\|\s*(\d+)mbps\s*Upload", re.I)


def scrape() -> list[NbnPlan]:
    soup = fetch_js(URL, settle_ms=6000)
    scraped_at = now_iso()

    table = soup.find("table")
    if table is None:
        raise RuntimeError("scrape() could not find the plans table")
    rows = table.find_all("tr")[1:]  # skip the header row

    plans = []
    section = "standard"
    for row in rows:
        cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
        if len(cells) < 4:
            continue
        name_text, price_text, typical_down_text, typical_up_text = cells[:4]

        if "eSLA" in name_text:
            section = "business"
        elif "Fixed Wireless" in name_text:
            section = "fixed_wireless"
        elif section == "fixed_wireless":
            # first unmarked row after Fixed Wireless is the start of the
            # (unlabeled) FTTP-only section
            section = "fttp_only"

        if section in ("fixed_wireless", "business"):
            continue

        plan_m = PLAN_RE.search(name_text)
        if not plan_m:
            continue
        down_mbps, up_mbps = plan_m.groups()

        price_m = re.search(r"\$(\d+\.?\d*)", price_text)
        typical_down_m = re.search(r"(\d+)", typical_down_text)
        if not (price_m and typical_down_m):
            continue

        plans.append(
            NbnPlan(
                provider=PROVIDER,
                plan_name=f"NBN {down_mbps}/{up_mbps}",
                price_monthly=float(price_m.group(1)),
                promo_price=None,
                promo_period_months=None,
                contract_length="No lock-in contract",
                speed_tier=f"NBN {down_mbps}/{up_mbps}",
                typical_evening_speed_mbps=float(typical_down_m.group(1)),
                tech_type=classify_tech_type(name_text),
                source_url=URL,
                scraped_at=scraped_at,
            )
        )

    if not plans:
        raise RuntimeError("scrape() returned no plans")
    return plans
