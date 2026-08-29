"""Arctel NBN plans scraper. Static HTML, no JS rendering needed.

Arctel is a budget nbn(R) brand launched in 2025 by Superloop, marketed as
"Your Trusted nbn Provider" on a WordPress/WooCommerce/Elementor site (not a
JS SPA). The homepage's address-eligibility checker only gates order
flow/serviceability (and resolves which of FTTP/HFC/FTTC/FTTN a given address
will connect over) -- the five residential speed-tier plan cards themselves,
including live/promo pricing and typical evening speeds, all render directly
into the static HTML with no address entry required.

The plan cards share a WooCommerce product wrapper
(`data-elementor-type="product"`) with an unrelated "Select Your Hardware"
upsell carousel further down the same page (an eero 7 modem add-on) that uses
near-identical Elementor markup. They're disambiguated by WooCommerce product
category: real plans carry a `product_cat-broadband` class, the modem upsell
carries `product_cat-modem` instead.

Each card's advertised nbn(R) speed tier (e.g. "25 Mbps" / "DOWNLOAD" and
"10 Mbps" / "UPLOAD") lives in two separate <h3>/<sup> widget pairs, not as a
single "25/10" string anywhere in visible text, so it's pulled with a regex
over the card's raw HTML rather than get_text(). The "Typical evening speed"
figure (7pm-11pm) appears separately as a "<down>/<up> Mbps" string and can
differ from the advertised tier -- e.g. Hyper Sonic advertises 1000/100 but
states a typical evening speed of only 860/86.

Two plans (Super Fast, Hyper Sonic) run an introductory promo, disclosed only
as free text like "$25 off for the first 6 months, then $84.99" next to the
already-discounted headline price -- the headline WooCommerce price is the
promo price, and the "then $X" figure is the true regular/ongoing price.
Plans with no such "then $X" text (Cruisy Lite, Cruisy, Ultra Fast) just
advertise a flat regular price with no promo.

Per-address connection technology (FTTP/HFC/FTTC/FTTN) is only resolved by
the JS address-eligibility checker at order time and isn't disclosed against
any specific plan in the static markup, so tech_type is left unset here.
"""
import re

from scraper.base import fetch_static, parse_price
from scraper.schema import NbnPlan, now_iso

PROVIDER = "Arctel"
URL = "https://arctel.com.au/"
REQUIRES_JS = False

DOWNLOAD_RE = re.compile(r"([\d.]+)\s*Mbps</span></h3>\s*<p><sup>DOWNLOAD</sup>")
UPLOAD_RE = re.compile(r"([\d.]+)\s*Mbps</span></h3>\s*<p><sup>UPLOAD</sup>")
TYPICAL_RE = re.compile(r"Typical evening speed:\s*([\d.]+)\s*/\s*([\d.]+)\s*Mbps")
PROMO_RE = re.compile(r"off for the first (\d+) months?,\s*then\s*\$([\d.]+)")


def scrape() -> list[NbnPlan]:
    soup = fetch_static(URL)
    # Check new slick slider markup first, fallback to legacy elementor product div
    cards = soup.find_all("article", class_="product-slider")
    if not cards:
        cards = [
            card
            for card in soup.find_all("div", attrs={"data-elementor-type": "product"})
            if "product_cat-broadband" in (card.get("class") or [])
        ]

    by_tier: dict[str, NbnPlan] = {}
    scraped_at = now_iso()
    for card in cards:
        name_el = card.find("h3", class_="card__name") or card.find("h2", class_="elementor-heading-title")
        if not name_el:
            continue

        # Extract speeds: check modern .speed containers first
        down_mbps = None
        up_mbps = None
        for s_div in card.find_all("div", class_="speed"):
            s_text = s_div.get_text(" ", strip=True)
            if "download" in s_text.lower():
                m = re.search(r"(\d+(?:\.\d+)?)\s*Mbps", s_text, re.I)
                if m:
                    down_mbps = m.group(1)
            elif "upload" in s_text.lower():
                m = re.search(r"(\d+(?:\.\d+)?)\s*Mbps", s_text, re.I)
                if m:
                    up_mbps = m.group(1)

        # Fallback to legacy regex on card HTML
        card_html = str(card)
        if not (down_mbps and up_mbps):
            down_match = DOWNLOAD_RE.search(card_html)
            up_match = UPLOAD_RE.search(card_html)
            if down_match and up_match:
                down_mbps = down_match.group(1)
                up_mbps = up_match.group(1)

        # Fallback to SKU pattern (e.g. ARC-SUPER-FAST-500-50)
        if not (down_mbps and up_mbps):
            btn = card.find("div", class_="arc-select-broadband-plan")
            if btn and btn.get("data-sku"):
                sku_m = re.search(r"-(\d+)-(\d+)", btn.get("data-sku"))
                if sku_m:
                    down_mbps, up_mbps = sku_m.group(1), sku_m.group(2)

        if not (down_mbps and up_mbps):
            continue

        # Extract pricing
        price_btn = card.find("div", class_="arc-select-broadband-plan")
        data_price = float(price_btn.get("data-price")) if (price_btn and price_btn.get("data-price")) else None
        price_el = (
            card.find("span", class_="arc-wc-price")
            or card.find("p", class_="price")
            or card.find("div", class_="price")
        )
        headline_price = data_price or (parse_price(price_el.get_text(strip=True)) if price_el else None)
        if headline_price is None:
            continue

        text = card.get_text(" ", strip=True)
        typical_match = TYPICAL_RE.search(text)
        promo_match = PROMO_RE.search(text)
        if not promo_match:
            promo_match = re.search(r"(?:off for the first|for)\s+(\d+)\s+months?(?:,\s*then\s*\$([\d.]+))?", text, re.I)

        if promo_match and promo_match.group(2):
            promo_months = int(promo_match.group(1))
            regular_price = float(promo_match.group(2))
            promo_price = headline_price
        else:
            promo_months = None
            regular_price = headline_price
            promo_price = None

        speed_tier = f"NBN {down_mbps}/{up_mbps}"
        plan = NbnPlan(
            provider=PROVIDER,
            plan_name=name_el.get_text(strip=True),
            price_monthly=regular_price,
            promo_price=promo_price,
            promo_period_months=promo_months,
            contract_length="No lock-in contract",
            speed_tier=speed_tier,
            typical_evening_speed_mbps=float(typical_match.group(1)) if typical_match else None,
            source_url=URL,
            scraped_at=scraped_at,
        )

        existing = by_tier.get(speed_tier)
        if existing is None:
            by_tier[speed_tier] = plan
        else:
            existing_effective = existing.promo_price or existing.price_monthly
            new_effective = plan.promo_price or plan.price_monthly
            if new_effective < existing_effective:
                by_tier[speed_tier] = plan

    plans = list(by_tier.values())
    if not plans:
        raise RuntimeError("scrape() could not parse any plans from the Arctel homepage")
    return plans
