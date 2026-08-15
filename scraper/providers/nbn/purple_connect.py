"""Purple Connect (ELGAS) NBN plans scraper. Static PDF fetch, no JS rendering needed.

Purple Connect is a residential nbn(R) reseller brand operated by Carrier Access
Networks Pty Ltd, marketed under ELGAS's own domain (elgas.com.au/purple-connect)
even though it's an unrelated telco product to ELGAS's core LPG gas business.

Both the marketing page (elgas.com.au/purple-connect) and the actual order portal
(purpleconnect.elgas.com.au, a React SPA) are address-gated -- no plan names or
prices render until a real service address is entered via the "Enter your
address" flow. Following this project's Neptune Internet convention, this
instead scrapes the Critical Information Summary -- a regulatory disclosure
covering every plan Purple Connect offers, address-independent by law. Unlike
Neptune's CIS (an HTML page), Purple Connect's CIS is a PDF, linked from the
portal's own footer ("Legals" -> "Critical Information Summary") and hosted on
Purple Connect's own S3 asset bucket with no bot-mitigation in front of it, so a
plain `requests.get()` for the PDF bytes works fine -- no Playwright needed.

The CIS table lists 11 plan tiers total: 7 fixed-line (FTTN/B/C, FTTP, HFC)
plans plus 4 Fixed Wireless plans. Only the 7 fixed-line tiers are kept here,
matching this project's convention elsewhere (Dodo, Neptune) of excluding Fixed
Wireless as not a fixed-line NBN product.

The three newest/fastest fibre-only tiers (Superfast 500/50, Superfast II
750/50, Ultrafast 1000/100) are flagged in the CIS as "Maximum Speed Potential"
rather than a measured typical evening speed -- Purple Connect states they
don't yet have enough customer data to report a real busy-period figure for
these, so typical_evening_speed_mbps is left unset (None) for those three
rather than reporting their theoretical max as if it were a measured value.
"""
import io
import re
import time

import requests
from pypdf import PdfReader

from scraper.base import DEFAULT_BACKOFF_SECONDS, DEFAULT_RETRIES, DEFAULT_TIMEOUT, USER_AGENT
from scraper.base import FetchError, classify_tech_type, logger, parse_price
from scraper.schema import NbnPlan, now_iso

PROVIDER = "Purple Connect"
URL = "https://btb-storefront-purpleconnect-otherassets.s3.ap-southeast-2.amazonaws.com/Purple_Connect_CIS_NBN_v4.pdf"
REQUIRES_JS = False

# Table rows read "<name> <tech tokens> [Maximum Speed Potential <footnote>] Download
# <n> Mbps Upload <n> Mbps Unlimited $<price> $<price>" once whitespace is collapsed.
# Tech tokens are matched longest-first so "FTTN/B/C, FTTP, HFC" isn't cut short by
# the plain "FTTN/B/C" alternative.
ROW_RE = re.compile(
    r"([A-Za-z][A-Za-z0-9 /\-]*?)\s+"
    r"(FTTN/B/C,\s*FTTP,\s*HFC|FTTN/B/C|FTTP,\s*HFC|Fixed Wireless)\s+"
    r"(Maximum Speed Potential\s*\d?\s*)?"
    r"Download\s*(\d+)\s*Mbps\s*Upload\s*(\d+)\s*Mbps\s*"
    r"Unlimited\s*\$([\d.]+)\s*\$([\d.]+)"
)
TIER_RE = re.compile(r"(\d+)/(\d+)$")
# Anchor past the table header row -- without this, the greedy-adjacent header
# text ("...Minimum Monthly Charge 3 Maximum Monthly Charge 3") gets swallowed
# into the first row's non-greedy name capture.
HEADER_RE = re.compile(r"Maximum\s*Monthly\s*Charge\s*3")


def _fetch_pdf_bytes(url: str) -> bytes:
    """Download raw PDF bytes, with the same retry/backoff as fetch_static."""
    last_exc: Exception | None = None
    for attempt in range(1, DEFAULT_RETRIES + 1):
        try:
            resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=DEFAULT_TIMEOUT)
            resp.raise_for_status()
            return resp.content
        except requests.RequestException as exc:
            last_exc = exc
            logger.warning("_fetch_pdf_bytes attempt %d/%d failed for %s: %s", attempt, DEFAULT_RETRIES, url, exc)
            if attempt < DEFAULT_RETRIES:
                time.sleep(DEFAULT_BACKOFF_SECONDS * attempt)
    raise FetchError(f"Failed to fetch {url} after {DEFAULT_RETRIES} attempts") from last_exc


def scrape() -> list[NbnPlan]:
    pdf_bytes = _fetch_pdf_bytes(URL)
    reader = PdfReader(io.BytesIO(pdf_bytes))
    raw_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    # U+F0D2 is a private-use-area glyph the PDF uses for the nbn(R) trademark symbol.
    text = re.sub(r"\s+", " ", raw_text.replace("\uf0d2", ""))

    header_match = HEADER_RE.search(text)
    table_text = text[header_match.end():] if header_match else text

    plans = []
    scraped_at = now_iso()
    for match in ROW_RE.finditer(table_text):
        name, tech, max_speed_marker, down_mbps, up_mbps, min_charge, _max_charge = match.groups()
        if "Fixed Wireless" in tech:
            continue  # not a fixed-line NBN plan, same convention as Dodo/Neptune

        name = name.strip()
        tier_match = TIER_RE.search(name)
        if not tier_match:
            continue
        tier_down, tier_up = tier_match.groups()
        plan_name = TIER_RE.sub("", name).strip()

        plans.append(
            NbnPlan(
                provider=PROVIDER,
                plan_name=plan_name,
                price_monthly=parse_price(min_charge),
                promo_price=None,
                promo_period_months=None,
                contract_length="No lock-in contract",
                speed_tier=f"NBN {tier_down}/{tier_up}",
                typical_evening_speed_mbps=None if max_speed_marker else float(down_mbps),
                tech_type=classify_tech_type(tech),
                source_url=URL,
                scraped_at=scraped_at,
            )
        )

    if not plans:
        raise RuntimeError("scrape() could not parse any plans from the CIS PDF")
    return plans
