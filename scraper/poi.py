"""Public internet-exchange footprint scraper (community-requested POI proxy).

Community feature request (r/nbn, user "nofarius"): the same NBN plan can have
very different latency/congestion depending on which of NBN Co's POIs your
retailer actually interconnects at -- a retailer with only a Sydney/Melbourne
POI backhauls all other states' traffic interstate before it comes back,
"does wonders for latency" (sarcastically). Reddit's own suggested source is
Hurricane Electric's BGP Toolkit (bgp.he.net) IX tab for each retailer's ASN --
a neutral internet-routing registry aggregator, NOT a comparison site, so this
doesn't run into this project's "never scrape comparison sites" rule.

IMPORTANT naming/accuracy decision (2026-08-15, live-verified before shipping):
this data is each provider's PUBLIC internet-exchange peering footprint, not a
direct read of NBN Co's own POI list -- the two correlate for most resellers
but diverge badly for Tier-1/large carriers. Telstra, Optus, iiNet, Vodafone,
and Arctel/Triforce all show a genuinely empty IX table on bgp.he.net (verified
live, not a scrape bug) because they peer privately/directly rather than via
public exchanges -- despite having real nationwide infrastructure. Showing
"0 states" for them would be backwards and misleading (worse than the
CGNAT/notice-badge sourcing issue from earlier this project), so: the feature
is user-facing labelled "Public exchange footprint" (never "NBN POI" or
"coverage"), and any provider with an empty IX table is rendered as "Not
published via public exchanges" rather than a 0/blank state list. See
scrape_provider()'s docstring for the noPublicIxData flag this drives.

This is intentionally a SEPARATE, low-frequency update path from run.py's daily
plan scrape -- nofarius's own suggestion was "not something that changes often,
would probably only need to refresh once a month or 6". Run via update_poi.py,
likely on its own monthly (not daily) CI schedule.

Tricky part nofarius flagged: retailers riding a wholesaler's network. Where a
retailer has no ASN/IX footprint of its own, PROVIDER_ASN below points at the
wholesaler's ASN instead (via_wholesaler set) and that's what gets shown. Where
a retailer DOES have its own ASN, we trust its own IX table over any wholesale
commercial-arrangement press coverage -- e.g. Neptune Internet holds AS151660
with a genuine, verified 16-exchange footprint across 5 states in its own IX
table (EdgeIX/IX Australia/MegaIX in Adelaide/Brisbane/Melbourne/Perth/Sydney),
despite some backup-path wholesale arrangement with Superloop/Aussie Broadband
turning up in secondary sources -- the live BGP table is the ground truth for
"which state does this traffic actually reach", not a commercial contract.

ASN research (2026-08-15, WebSearch + direct bgp.he.net verification -- see
NOTES.md if that verification log is copied over): four providers have no ASN
of their own after searching bgp.he.net's search index and PeeringDB, so they
point at the parent/wholesaler they're confirmed to resell on:
  - Tangerine, More Telecom -> Aussie Broadband (AS4764), 2025 wholesale deal
  - Purple Connect -> Aussie Broadband (AS4764), via Telcoinabox white-label
  - amaysim -> Optus (AS7474), Optus-owned MVNO/reseller since 2021
  - Arctel -> Triforce/Dataknox (AS55736), route-origin lookup on its own
    announced prefixes (no Arctel-named ASN exists)
  - Dodo -> Vocus (AS4826) -- Dodo is part of Vocus Retail Australia.
    PeeringDB confirms AS9443 has no active IX fabrics of its own and routes
    all traffic via AS4826 IX links (46 public exchanges including WA-IX in Perth,
    NSW, VIC, QLD, SA, NT, TAS).
If any of these commercial arrangements change, this mapping needs updating --
it is NOT re-derived automatically.
"""
import logging
import re
from collections import defaultdict
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from scraper.base import DEFAULT_BACKOFF_SECONDS, DEFAULT_RETRIES, DEFAULT_TIMEOUT, USER_AGENT
from scraper.base import FetchError, logger as base_logger

import requests

logger = logging.getLogger("scraper.poi")

BGP_HE_URL = "https://bgp.he.net/AS{asn}"

# provider display name -> (asn to look up, "via" label if it's a wholesaler's
# ASN rather than the provider's own -- shown to users as "via <wholesaler>")
PROVIDER_ASN = {
    "Aussie Broadband": (4764, None),
    "Leaptel": (134090, None),
    "Superloop": (38195, None),
    "Exetel": (10143, None),
    "Tangerine": (4764, "Aussie Broadband"),
    "More Telecom": (4764, "Aussie Broadband"),
    "Swoop": (58511, None),
    "Neptune Internet": (151660, None),
    "Purple Connect": (4764, "Aussie Broadband"),
    "Telstra": (1221, None),
    "Optus": (7474, None),
    "Arctel": (55736, "Triforce/Dataknox"),
    "Flip": (133898, None),
    "Dodo": (4826, "Vocus"),
    "TPG": (7545, None),
    "iiNet": (4802, None),
    "SpinTel": (18390, None),
    "Vodafone": (133612, None),
    "amaysim": (7474, "Optus"),
}

# Exchange-city -> AU state/territory. bgp.he.net's IX "City" column uses the
# metro name (e.g. "Sydney"), never the state directly, so this is a manual
# lookup rather than something parseable from the page itself.
CITY_TO_STATE = {
    "Sydney": "NSW",
    "Newcastle": "NSW",
    "Wollongong": "NSW",
    "Melbourne": "VIC",
    "Geelong": "VIC",
    "Brisbane": "QLD",
    "Gold Coast": "QLD",
    "Sunshine Coast": "QLD",
    "Townsville": "QLD",
    "Perth": "WA",
    "Adelaide": "SA",
    "Hobart": "TAS",
    "Launceston": "TAS",
    "Canberra": "ACT",
    "Darwin": "NT",
}


def _fetch_as_page(asn: int) -> BeautifulSoup:
    url = BGP_HE_URL.format(asn=asn)
    last_exc: Exception | None = None
    for attempt in range(1, DEFAULT_RETRIES + 1):
        try:
            resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=DEFAULT_TIMEOUT)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "lxml")
        except requests.RequestException as exc:
            last_exc = exc
            logger.warning("_fetch_as_page attempt %d/%d failed for AS%d: %s", attempt, DEFAULT_RETRIES, asn, exc)
            if attempt < DEFAULT_RETRIES:
                import time as _time
                _time.sleep(DEFAULT_BACKOFF_SECONDS * attempt)
    raise FetchError(f"Failed to fetch {url} after {DEFAULT_RETRIES} attempts") from last_exc


def _parse_ix_table(soup: BeautifulSoup) -> list[dict]:
    """Find the IX table (columns: Exchange, CC, City, IPv4, IPv6) and return
    one dict per row. bgp.he.net renders several tables on the AS page (peers,
    prefixes, IX...) with no unique id, so the IX table is identified by its
    header row containing both "Exchange" and "City" -- the only table with
    that combination.
    """
    rows: list[dict] = []
    for table in soup.find_all("table"):
        header_cells = [th.get_text(strip=True) for th in table.find_all("th")]
        if "Exchange" in header_cells and "City" in header_cells:
            col_index = {name: i for i, name in enumerate(header_cells)}
            for tr in table.find_all("tr")[1:]:
                cells = tr.find_all("td")
                if len(cells) < len(header_cells):
                    continue
                exchange_cell = cells[col_index["Exchange"]]
                city_cell = cells[col_index["City"]]
                cc_cell = cells[col_index["CC"]] if "CC" in col_index else None
                exchange_name = exchange_cell.get_text(strip=True)
                city = city_cell.get_text(strip=True)
                cc = cc_cell.get_text(strip=True) if cc_cell is not None else None
                if exchange_name and city:
                    rows.append({"exchange": exchange_name, "city": city, "country": cc})
            break  # only one IX table per page
    return rows


def _rows_to_footprint(rows: list[dict]) -> dict:
    au_cities = sorted({r["city"] for r in rows if r.get("country") in (None, "AU")})
    states = sorted({CITY_TO_STATE[c] for c in au_cities if c in CITY_TO_STATE})
    unmapped_cities = sorted(c for c in au_cities if c not in CITY_TO_STATE)
    if unmapped_cities:
        logger.warning("Unmapped AU IX cities (add to CITY_TO_STATE): %s", unmapped_cities)
    return {
        "exchangeCount": len(rows),
        "cities": au_cities,
        "states": states,
    }


def scrape_provider(provider: str) -> dict:
    """Returns the public-exchange footprint dict for one provider. Raises on
    fetch failure -- caller (update_poi.py) decides whether to keep
    last-known-good.

    An empty IX table is NOT treated as an error. Verified live (2026-08-15)
    that Telstra (AS1221), Optus (AS7474), iiNet (AS4802), Vodafone (AS133612)
    and Arctel/Triforce (AS55736) all genuinely have zero rows in bgp.he.net's
    IX section -- Tier-1/large carriers mostly peer privately/directly rather
    than through public exchanges, so bgp.he.net's IX report has nothing to
    show for them despite their real-world footprint being nationwide. Showing
    "0 states" for these would be actively misleading (the opposite of their
    real coverage), so this is surfaced as noPublicIxData=True instead of a
    state list, and the site must render that as "not published via public
    exchanges" rather than "no coverage". This is why the feature is framed as
    "public internet exchange footprint" (a measurable, honestly-labelled
    proxy) rather than "NBN Point of Interconnect" (which this data is NOT a
    direct measurement of -- see module docstring).
    """
    asn, via = PROVIDER_ASN[provider]
    soup = _fetch_as_page(asn)
    rows = _parse_ix_table(soup)
    footprint = _rows_to_footprint(rows)
    footprint["asn"] = asn
    footprint["viaWholesaler"] = via
    footprint["sourceUrl"] = BGP_HE_URL.format(asn=asn)
    footprint["noPublicIxData"] = len(rows) == 0
    return footprint


def scrape_all() -> dict[str, dict]:
    results = {}
    for provider in PROVIDER_ASN:
        results[provider] = scrape_provider(provider)
    return results


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
