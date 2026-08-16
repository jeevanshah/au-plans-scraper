"""Future Broadband NBN plans scraper. Static HTML, no JS rendering needed.

Future Broadband (Digital Immortality Pty Ltd) is a Perth-founded boutique ISP
known on Whirlpool for low-contention NBN and static IP allocations (AS139084).
Their residential plans page embeds structured cards with class `pcp-card`:
  - `.pcp-title`: plan name (Lite, Starter, Everyday, Family, Boost, SuperFast, HyperFast, HyperFast+)
  - `.pcp-speeds`: nominal download & upload speeds
  - `.pcp-price-new`: monthly price
  - `.pcp-panel-value`: typical evening peak speeds
"""
import re

from scraper.base import fetch_static, normalize_nbn_speed_tier
from scraper.schema import NbnPlan, now_iso

PROVIDER = "Future Broadband"
URL = "https://futurebroadband.com.au/residential/"
REQUIRES_JS = False

PRICE_RE = re.compile(r"\$\s*(\d+\.?\d*)")
SPEED_VAL_RE = re.compile(r"(\d+)")
EVENING_RE = re.compile(r"(\d+)(?:/\d+)?\s*Mbps", re.I)


def scrape() -> list[NbnPlan]:
    soup = fetch_static(URL)
    scraped_at = now_iso()

    cards = soup.find_all("div", class_=lambda c: c and "pcp-card" in c)
    plans: list[NbnPlan] = []
    seen_plans: set[str] = set()

    for card in cards:
        title_el = card.find(class_=lambda c: c and "pcp-title" in c)
        marketing_name = title_el.get_text(strip=True) if title_el else "NBN"

        # Price
        price_el = card.find(class_=lambda c: c and "pcp-price-new" in c)
        if not price_el:
            continue
        price_text = price_el.get_text(strip=True)
        m_price = PRICE_RE.search(price_text)
        if not m_price:
            continue
        price_monthly = float(m_price.group(1))

        # Speeds
        speeds_el = card.find(class_=lambda c: c and "pcp-speeds" in c)
        if not speeds_el:
            continue
        speed_items = speeds_el.find_all(class_=lambda c: c and "pcp-speed-item" in c)
        if len(speed_items) < 2:
            continue

        down_val_el = speed_items[0].find(class_=lambda c: c and "pcp-speed-value" in c)
        up_val_el = speed_items[1].find(class_=lambda c: c and "pcp-speed-value" in c)
        if not down_val_el or not up_val_el:
            continue

        m_down = SPEED_VAL_RE.search(down_val_el.get_text(strip=True))
        m_up = SPEED_VAL_RE.search(up_val_el.get_text(strip=True))
        if not m_down or not m_up:
            continue

        raw_down = int(m_down.group(1))
        raw_up = int(m_up.group(1))

        speed_tier, _, _ = normalize_nbn_speed_tier(raw_down, raw_up)

        # Evening speed
        panel_val = card.find(class_=lambda c: c and "pcp-panel-value" in c)
        evening_speed = float(raw_down)
        if panel_val:
            m_eve = EVENING_RE.search(panel_val.get_text(" ", strip=True))
            if m_eve:
                evening_speed = float(m_eve.group(1))

        tech_type = "Fibre" if raw_down >= 500 else "Fibre and FTTN"

        plan_key = f"{marketing_name}-{speed_tier}-{price_monthly}"
        if plan_key in seen_plans:
            continue
        seen_plans.add(plan_key)

        plans.append(
            NbnPlan(
                provider=PROVIDER,
                plan_name=f"{marketing_name} {speed_tier}",
                price_monthly=price_monthly,
                promo_price=None,
                promo_period_months=None,
                promo_end_date=None,
                contract_length="No lock-in contract",
                speed_tier=speed_tier,
                typical_evening_speed_mbps=evening_speed,
                tech_type=tech_type,
                source_url=URL,
                scraped_at=scraped_at,
            )
        )

    if not plans:
        raise RuntimeError("scrape() could not extract any plans from Future Broadband page")
    return plans
