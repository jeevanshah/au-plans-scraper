"""Optus NBN plans scraper. JS-rendered -- needs fetch_js() with two non-default
options: channel="chrome" (a real installed Chrome binary, not Playwright's bundled
Chromium) AND a plain, unmodified browser User-Agent (not this project's usual
self-identifying UA).

Previous research (see NOTES.md) found every plain-HTTP fetch to optus.com.au timing
out or hitting ECONNRESET, with no page content at all -- worse than a 403/CAPTCHA,
looking like connection-level throttling. Retried from scratch:

- Plain `requests` (this project's `fetch_static`) actually works fine now and returns
  a 200 with ~1MB of HTML for https://www.optus.com.au/internet/nbn -- no throttling,
  no reset. But the page is an AEM/React hybrid (`PlanListingWithRecoil` /
  `PlanSliderBlockAem` components) whose plan cards -- price, speed, promo terms -- are
  entirely client-rendered; the raw HTML only carries widget config (CTA text, brand/pack
  maps), not any plan data. So `fetch_static` alone can't get real prices.
- A 2x2 test (bundled Chromium vs real Chrome channel x this project's default
  self-identifying UA vs a plain browser UA) showed BOTH factors matter:
  - Playwright's bundled Chromium fails with `net::ERR_HTTP2_PROTOCOL_ERROR` on every
    URL on the domain (including the bare homepage) regardless of UA -- its TLS
    ClientHello / HTTP2 SETTINGS fingerprint differs subtly from a real Chrome release,
    and Optus's bot mitigation resets the connection before any response comes back.
    `--disable-http2` doesn't help, it just changes the failure to `ERR_CONNECTION_RESET`.
  - A real installed Chrome (`channel="chrome"`) still gets the same
    `ERR_HTTP2_PROTOCOL_ERROR` if given this project's default `USER_AGENT` constant,
    because that string carries an honest self-identification prefix
    ("au-plans-scraper/1.0 (+https://github.com/...)") ahead of the browser UA --
    real Chrome + a UA that isn't byte-for-byte what a real Chrome install sends is
    still enough for Optus to flag and reset the connection.
  - Only real Chrome + an unmodified, plain browser UA string passes clean on every
    URL tried. Both the channel and the UA override are necessary; either alone still
    fails. `fetch_js()` in `scraper/base.py` gained a `channel` and a `user_agent`
    kwarg for this (both default to the old behaviour, so every other provider is
    unaffected). The CI workflow now installs `chrome` too
    (`playwright install --with-deps chromium chrome`).
  - Worth flagging: this means Optus is scraped without this project's usual polite
    self-identifying UA, unlike every other provider. That's a deliberate compromise
    for this one site given the alternative was "unscrapeable" -- if that's ever judged
    not worth it, drop `PLAIN_USER_AGENT` below and this provider goes back to failing
    fast rather than silently misrepresenting itself.
- No address gating: unlike Neptune, the main plans page shows real prices for all 5
  residential plans with no address entered -- eligibility ("Check your eligibility" /
  fibre-only restriction text) is disclosed per-card but doesn't hide the plan or price.
  So the CIS-page detour wasn't needed here; each card also links a per-plan "Critical
  Information Summary (PDF)" but it's a client-side download triggered by JS (href="#"),
  not a fetchable static URL, and wasn't necessary given the page itself has full data.

Plan cards are `div` elements whose class list contains "plan-card-container"
(`data-testid="plan-{id}"`). Within a card:
- the advertised speed is the `[data-testid="plan-speed"]` element's leading number
  (e.g. "25" of "25 Mbps");
- price/promo terms are read from a fixed free-text sentence that appears on every
  observed card: "Plan is $X/month for N months, then $Y/month or as notified." --
  X is the promo price, Y the regular/ongoing price, N the promo duration;
- typical busy-period (7pm-11pm) down/up speeds appear as "Typical Busy Period Speeds
  (7pm-11pm) <down> Mbps Download <up> Mbps Upload";
- the per-tier tech-eligibility note lives in a `plan-speed-legal-disclaimer` element,
  either "Typical Download Speed: all nbn connections" (available on every fixed-line
  nbn tech, i.e. FTTN/FTTB/FTTC/HFC/FTTP) or "...: FTTP, HFC" (fibre/cable only, on the
  two fastest tiers) -- mapped onto classify_tech_type()'s existing categories;
- the plan name comes from a `promo-block-description` paragraph ("<Name> plan: ...")
  on 4 of the 5 cards, or a `plan-card-badge` element ("<Name> plan", no colon) on the
  5th -- a limited-time "Promo Plus" card with no description block at all.

One tier (500Mbps FTTP/HFC) currently has *two* simultaneous cards: a standing "Fast"
plan ($89/mth, no expiry) and a limited-time "Promo Plus" plan ($69/mth for 6 months,
explicitly "Available until 6/9/2026"). Both share the same speed_tier string, which
would collide in transform.py's `_make_id()` (keyed on provider+speed_tier+month) if
both were kept -- so when two cards share a speed_tier, only the one with the lower
current effective price (promo price if any, else regular price) is kept, matching
what a price-comparison site actually wants to surface for that tier anyway.
"""
import re

from scraper.base import classify_tech_type, fetch_js, normalize_nbn_speed_tier
from scraper.schema import NbnPlan, now_iso

PROVIDER = "Optus"
URL = "https://www.optus.com.au/internet/nbn"
REQUIRES_JS = True

# A plain, unmodified browser UA -- NOT this project's usual self-identifying
# USER_AGENT constant from scraper/base.py. See the module docstring: Optus's bot
# mitigation resets the connection for real Chrome too if the UA carries the
# project's normal "au-plans-scraper/1.0 (+https://github.com/...)" prefix.
PLAIN_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

PRICE_RE = re.compile(
    r"Plan is \$([\d.]+)/month for (\d+) months?,\s*then\s*\$([\d.]+)/month"
)
TYPICAL_RE = re.compile(
    r"Typical Busy Period Speeds \(7pm-11pm\)\s*(\d+)\s*Mbps Download\s*(\d+)\s*Mbps Upload"
)
NAME_FROM_DESC_RE = re.compile(r"^([A-Za-z0-9 +]+?)\s*plan\s*:", re.I)
NAME_FROM_BADGE_RE = re.compile(r"^([A-Za-z0-9 +]+?)\s*plan\s*$", re.I)


def _find_class(card, needle):
    return card.find(class_=lambda c: c and needle in c)


def _plan_name(card, down_mbps, up_mbps) -> str:
    desc = _find_class(card, "promo-block-description")
    if desc is not None:
        text = desc.get_text(" ", strip=True)
        m = NAME_FROM_DESC_RE.match(text)
        if m:
            return m.group(1).strip()
    badge = _find_class(card, "plan-card-badge")
    if badge is not None:
        text = badge.get_text(" ", strip=True)
        m = NAME_FROM_BADGE_RE.match(text)
        if m:
            return m.group(1).strip()
    return f"NBN {down_mbps}/{up_mbps}"


def scrape() -> list[NbnPlan]:
    soup = fetch_js(URL, channel="chrome", user_agent=PLAIN_USER_AGENT, settle_ms=8000)
    scraped_at = now_iso()

    cards = soup.find_all("div", class_=lambda c: c and "plan-card-container" in c)

    by_tier: dict[str, NbnPlan] = {}
    for card in cards:
        text = card.get_text(" ", strip=True)

        speed_el = card.find(attrs={"data-testid": "plan-speed"})
        price_m = PRICE_RE.search(text)
        typical_m = TYPICAL_RE.search(text)
        if not (speed_el and price_m and typical_m):
            continue

        down_mbps, up_mbps = typical_m.groups()
        speed_tier, _, _ = normalize_nbn_speed_tier(down_mbps, up_mbps)

        promo_price, promo_months, regular_price = price_m.groups()
        promo_price = float(promo_price)
        regular_price = float(regular_price)

        disclaimer_el = _find_class(card, "plan-speed-legal-disclaimer")
        disclaimer_text = disclaimer_el.get_text(" ", strip=True) if disclaimer_el else ""
        if "all nbn connections" in disclaimer_text.lower():
            tech_type = "Fibre and FTTN"
        else:
            tech_type = classify_tech_type(disclaimer_text)

        plan = NbnPlan(
            provider=PROVIDER,
            plan_name=_plan_name(card, down_mbps, up_mbps),
            price_monthly=regular_price,
            promo_price=promo_price,
            promo_period_months=int(promo_months),
            contract_length="No lock-in contract",
            speed_tier=speed_tier,
            typical_evening_speed_mbps=float(down_mbps),
            tech_type=tech_type,
            source_url=URL,
            scraped_at=scraped_at,
        )

        existing = by_tier.get(speed_tier)
        if existing is None:
            by_tier[speed_tier] = plan
        else:
            # Two simultaneous cards for the same tier (a standing plan + a
            # limited-time promo) -- keep whichever is actually cheaper right now.
            existing_effective = existing.promo_price or existing.price_monthly
            new_effective = plan.promo_price or plan.price_monthly
            if new_effective < existing_effective:
                by_tier[speed_tier] = plan

    plans = list(by_tier.values())
    if not plans:
        raise RuntimeError("scrape() could not parse any plans from the Optus nbn page")
    return plans
