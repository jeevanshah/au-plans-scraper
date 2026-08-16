"""Shared fetch helpers for provider scrapers."""
import logging
import re
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger("scraper")

USER_AGENT = (
    "au-plans-scraper/1.0 (+https://github.com/; contact: see repo README) "
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

DEFAULT_TIMEOUT = 20
DEFAULT_RETRIES = 3
DEFAULT_BACKOFF_SECONDS = 2


class FetchError(RuntimeError):
    """Raised when a page can't be retrieved after retries."""


def fetch_static(url: str, *, retries: int = DEFAULT_RETRIES) -> BeautifulSoup:
    """Fetch a URL and return parsed HTML. Retries with backoff on failure."""
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=DEFAULT_TIMEOUT,
            )
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "lxml")
        except requests.RequestException as exc:
            last_exc = exc
            logger.warning("fetch_static attempt %d/%d failed for %s: %s", attempt, retries, url, exc)
            if attempt < retries:
                time.sleep(DEFAULT_BACKOFF_SECONDS * attempt)
    raise FetchError(f"Failed to fetch {url} after {retries} attempts") from last_exc


def fetch_js(
    url: str,
    *,
    wait_selector: str | None = None,
    wait_until: str = "load",
    settle_ms: int = 0,
    timeout_ms: int = 45000,
    retries: int = DEFAULT_RETRIES,
    channel: str | None = None,
    user_agent: str | None = None,
) -> BeautifulSoup:
    """Fetch a JS-rendered page via Playwright. Only used by providers with requires_js=True.

    wait_until defaults to "load" rather than "networkidle" -- some sites (e.g. TPG) never
    go network-idle due to background polling, which hangs "networkidle" until timeout.
    settle_ms adds a fixed extra wait after load/selector for client-side hydration that
    finishes just after the load event (e.g. Superloop's Gatsby+React plan cards).

    channel lets a provider request a real installed browser (e.g. "chrome") instead of
    Playwright's bundled Chromium-for-Testing build, and user_agent overrides the module's
    self-identifying default UA. Optus needs both: its bot mitigation fingerprints at the
    TLS/HTTP2 layer and resets the connection (net::ERR_HTTP2_PROTOCOL_ERROR) for the
    bundled Chromium build regardless of UA, AND (separately) for a real Chrome binary
    if it's sent this module's default USER_AGENT, which -- unlike a normal browser UA --
    carries an honest "au-plans-scraper/1.0 (+https://github.com/...)" self-identification
    prefix; only real Chrome + a plain, unmodified browser UA string passes. See
    scraper/providers/nbn/optus.py and NOTES.md for the full 2x2 test that isolated this.
    The CI workflow installs both `chromium` and `chrome` via `playwright install` so the
    "chrome" channel is available there too.
    """
    from playwright.sync_api import sync_playwright

    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(channel=channel)
                try:
                    page = browser.new_page(user_agent=user_agent or USER_AGENT)
                    page.goto(url, timeout=timeout_ms, wait_until=wait_until)
                    if wait_selector:
                        page.wait_for_selector(wait_selector, timeout=timeout_ms)
                    if settle_ms:
                        page.wait_for_timeout(settle_ms)
                    html = page.content()
                finally:
                    browser.close()
            return BeautifulSoup(html, "lxml")
        except Exception as exc:
            last_exc = exc
            logger.warning("fetch_js attempt %d/%d failed for %s: %s", attempt, retries, url, exc)
            if attempt < retries:
                time.sleep(DEFAULT_BACKOFF_SECONDS * attempt)
    raise FetchError(f"Failed to fetch (js) {url} after {retries} attempts") from last_exc


_MONTH_END_DATE_RE = re.compile(
    r"Ends (\d{1,2}) (January|February|March|April|May|June|July|August|September|October|November|December)"
)


def parse_relative_end_date(text: str, scraped_at: str) -> str | None:
    """Extract a promo end-date like 'Ends 10 August' -> ISO date, inferring the year
    from scraped_at (rolling forward a year if that date has already passed)."""
    match = _MONTH_END_DATE_RE.search(text)
    if not match:
        return None

    day, month_name = match.groups()
    scraped_dt = datetime.fromisoformat(scraped_at)
    candidate = datetime.strptime(f"{day} {month_name} {scraped_dt.year}", "%d %B %Y")
    if candidate.date() < scraped_dt.date():
        candidate = candidate.replace(year=scraped_dt.year + 1)
    return candidate.date().isoformat()


def classify_tech_type(text: str) -> str | None:
    """Best-effort NBN connection-tech label from disclosure text on a plan card.
    Returns None rather than guessing when no eligibility text is present at all."""
    if "FTTN" in text or "FTTB" in text or "FTTC" in text or "All Fixed-Line" in text:
        return "Fibre and FTTN"
    if "FTTP" in text or "HFC" in text:
        return "Fibre"
    return None


_ABS_END_DATE_RE = re.compile(r"[Oo]ffer ends (\d{1,2}) (\w+) (\d{4})")


def parse_absolute_end_date(text: str) -> str | None:
    """Extract a promo end-date like 'Offer ends 1 Sep 2026' -> ISO date."""
    match = _ABS_END_DATE_RE.search(text)
    if not match:
        return None
    day, month_name, year = match.groups()
    for fmt in ("%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(f"{day} {month_name} {year}", fmt).date().isoformat()
        except ValueError:
            continue
    return None


def parse_price(text: str) -> float:
    """Extract a dollar amount like '$79/mth' or '$79.00' -> 79.0."""
    cleaned = "".join(ch for ch in text if ch.isdigit() or ch == ".")
    if not cleaned:
        raise ValueError(f"No numeric price found in: {text!r}")
    return float(cleaned)


def normalize_nbn_speed_tier(down: float | int, up: float | int | None = None) -> tuple[str, float | None, float | None]:
    """Given an advertised download and optional upload speed (whether nominal or evening average),
    returns (nominal_speed_tier, typical_evening_down, typical_evening_up)."""
    down_f = float(down)
    up_f = float(up) if up is not None else None

    if down_f <= 15:
        nom_down = 12
        nom_up = 1
    elif down_f <= 35:
        nom_down = 25
        nom_up = 10 if (up_f is None or up_f > 6) else 5
    elif down_f <= 65:
        nom_down = 50
        nom_up = 20
    elif down_f <= 160:
        nom_down = 100
        nom_up = 40 if (up_f is not None and up_f >= 30) else 20
    elif down_f <= 350:
        nom_down = 250
        nom_up = 100 if (up_f is not None and up_f >= 80) else 25
    elif down_f <= 600:
        nom_down = 500
        nom_up = 200 if (up_f is not None and up_f >= 150) else 50
    elif down_f <= 790 and (up_f is None or up_f <= 60):
        nom_down = 750
        nom_up = 50
    elif down_f <= 1400:
        nom_down = 1000
        if up_f is not None and up_f >= 300:
            nom_up = 400
        elif up_f is not None and up_f <= 60:
            nom_up = 50
        else:
            nom_up = 100
    else:
        nom_down = 2000
        if up_f is not None and up_f >= 400:
            nom_up = 500
        elif up_f is not None and up_f >= 180:
            nom_up = 200
        else:
            nom_up = 100

    tier = f"NBN {nom_down}/{nom_up}"
    return tier, down_f, up_f
