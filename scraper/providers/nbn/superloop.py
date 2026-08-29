"""Superloop NBN plans scraper.

Superloop's plan cards are a Gatsby+React page that renders empty on a plain
static fetch and even right after Playwright's "load" event -- the cards
hydrate a moment later, so fetch_js needs an explicit settle_ms wait.
"""
import re

from scraper.base import fetch_js, parse_price
from scraper.schema import NbnPlan, now_iso

PROVIDER = "Superloop"
URL = "https://www.superloop.com/internet/nbn/"
REQUIRES_JS = True

SPEED_RE = re.compile(r"Download\s*(\d+)\s*Mbps\s*Upload\s*(\d+)\s*Mbps", re.I)
PRICE_RE = re.compile(r"\$(\d+(?:\.\d+)?)\s*\$(\d+(?:\.\d+)?)\s*/mth", re.I)
SINGLE_PRICE_RE = re.compile(r"\$(\d+(?:\.\d+)?)\s*/mth", re.I)
PROMO_MONTHS_RE = re.compile(r"For\s+(?:the\s+)?first\s+(\d+)\s+months?\s+then", re.I)
TYPICAL_SPEED_RE = re.compile(r"Typical evening speed\s*(\d+)(?:/[\d.]+)?\s*Mbps", re.I)


def scrape() -> list[NbnPlan]:
    soup = fetch_js(URL, settle_ms=4000)
    cards = soup.find_all("div", class_=lambda c: c and "shadow-md" in c and "bg-white" in c)
    if not cards:
        candidate_blocks = soup.find_all(lambda tag: tag.name == "div" and tag.get("class") and "group" in tag.get("class"))
        if not candidate_blocks:
            candidate_blocks = [
                d
                for d in soup.find_all("div")
                if SPEED_RE.search(d.get_text(" ", strip=True)) and "/mth" in d.get_text(" ", strip=True)
            ]
        cards = []
        for d in candidate_blocks:
            d_text = d.get_text(" ", strip=True)
            if SPEED_RE.search(d_text) and "/mth" in d_text:
                cards.append(d)

    plans = []
    scraped_at = now_iso()
    seen = set()

    for card in cards:
        text = card.get_text(" ", strip=True)
        name_el = card.find(["h3", "h2", "h4"])
        speed_match = SPEED_RE.search(text)
        if not speed_match:
            continue

        down_mbps, up_mbps = speed_match.groups()
        tier_key = f"{down_mbps}/{up_mbps}"

        plan_name = name_el.get_text(strip=True) if name_el else None
        if not plan_name or plan_name.lower() in ["basic", "power", "ultra", "download", "upload"]:
            for candidate in ["Everyday", "Extra Value", "Family Max", "Megaspeed", "Lightspeed", "Power", "Creator", "Hyperspeed"]:
                if candidate in text:
                    plan_name = candidate
                    break

        if not plan_name:
            continue

        if (plan_name, tier_key) in seen:
            continue
        seen.add((plan_name, tier_key))

        price_match = PRICE_RE.search(text)
        promo_months_match = PROMO_MONTHS_RE.search(text)
        typical_match = TYPICAL_SPEED_RE.search(text)

        if price_match:
            regular_price = parse_price(price_match.group(1))
            promo_price = parse_price(price_match.group(2))
            promo_months = int(promo_months_match.group(1)) if promo_months_match else None
        else:
            single_m = SINGLE_PRICE_RE.search(text)
            if not single_m:
                continue
            regular_price = parse_price(single_m.group(1))
            promo_price = None
            promo_months = None

        plans.append(
            NbnPlan(
                provider=PROVIDER,
                plan_name=plan_name,
                price_monthly=regular_price,
                promo_price=promo_price,
                promo_period_months=promo_months,
                contract_length="No lock-in contract",
                speed_tier=f"NBN {down_mbps}/{up_mbps}",
                typical_evening_speed_mbps=float(typical_match.group(1)) if typical_match else None,
                source_url=URL,
                scraped_at=scraped_at,
            )
        )
    return plans
