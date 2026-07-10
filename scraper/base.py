"""Shared fetch helpers for provider scrapers."""
import logging
import time

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
    timeout_ms: int = 45000,
    retries: int = DEFAULT_RETRIES,
) -> BeautifulSoup:
    """Fetch a JS-rendered page via Playwright. Only used by providers with requires_js=True."""
    from playwright.sync_api import sync_playwright

    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                try:
                    page = browser.new_page(user_agent=USER_AGENT)
                    page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
                    if wait_selector:
                        page.wait_for_selector(wait_selector, timeout=timeout_ms)
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


def parse_price(text: str) -> float:
    """Extract a dollar amount like '$79/mth' or '$79.00' -> 79.0."""
    cleaned = "".join(ch for ch in text if ch.isdigit() or ch == ".")
    if not cleaned:
        raise ValueError(f"No numeric price found in: {text!r}")
    return float(cleaned)
