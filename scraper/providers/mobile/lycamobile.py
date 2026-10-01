"""Lyca Mobile prepaid mobile plans scraper with Commission Factory affiliate tracking.

Covers 28-day prepaid SIM tiers (LycaPlan S, M, XL) and long-term
packs (180-day and 360-day options).
All plans run on the Vodafone 4G/5G mobile network.
Affiliate tracking routes via Commission Factory (Affiliate: 94613, Merchant: 45861).
"""
import urllib.parse
from scraper.schema import MobilePlan, now_iso

PROVIDER = "Lyca Mobile"
URL = "https://www.lycamobile.com.au/en/bundles/prepaid-plans/"
REQUIRES_JS = False

AFFILIATE_BASE = "https://t.cfjump.com/94613/t/45861"

PLANS_CONFIG = [
    {
        "plan_name": "LycaPlan S",
        "url": "https://www.lycamobile.com.au/en/bundle/unlimited-plan-s/",
        "data_gb": 50.0,
        "promo_price": 15.00,
        "regular_price": 30.00,
        "promo_months": 6,
        "billing_cycle_days": 28,
        "contract": "28-day expiry",
    },
    {
        "plan_name": "LycaPlan M",
        "url": "https://www.lycamobile.com.au/en/bundle/unlimited-plan-m/",
        "data_gb": 120.0,
        "promo_price": 20.00,
        "regular_price": 40.00,
        "promo_months": 6,
        "billing_cycle_days": 28,
        "contract": "28-day expiry",
    },
    {
        "plan_name": "LycaPlan XL",
        "url": "https://www.lycamobile.com.au/en/bundle/unlimited-plan-xl/",
        "data_gb": 300.0,
        "promo_price": None,
        "regular_price": 50.00,
        "promo_months": None,
        "billing_cycle_days": 28,
        "contract": "28-day expiry",
    },
    {
        "plan_name": "6-Month Long-Term Small",
        "url": "https://www.lycamobile.com.au/en/bundle/small/",
        "data_gb": 120.0,
        "promo_price": 90.00,
        "regular_price": 120.00,
        "promo_months": 6,
        "billing_cycle_days": 180,
        "contract": "180-day expiry",
    },
    {
        "plan_name": "12-Month Long-Term Medium",
        "url": "https://www.lycamobile.com.au/en/bundle/medium/",
        "data_gb": 360.0,
        "promo_price": 150.00,
        "regular_price": 240.00,
        "promo_months": 12,
        "billing_cycle_days": 360,
        "contract": "360-day expiry",
    },
    {
        "plan_name": "12-Month Long-Term Large",
        "url": "https://www.lycamobile.com.au/en/bundle/large/",
        "data_gb": 900.0,
        "promo_price": 220.00,
        "regular_price": 480.00,
        "promo_months": 12,
        "billing_cycle_days": 360,
        "contract": "360-day expiry",
    },
]


def make_affiliate_url(direct_url: str) -> str:
    return f"{AFFILIATE_BASE}?Url={urllib.parse.quote(direct_url, safe='')}"


def scrape() -> list[MobilePlan]:
    scraped_at = now_iso()
    plans: list[MobilePlan] = []

    for cfg in PLANS_CONFIG:
        affiliate_url = make_affiliate_url(cfg["url"])
        plans.append(
            MobilePlan(
                provider=PROVIDER,
                plan_name=cfg["plan_name"],
                price_monthly=cfg["regular_price"],
                promo_price=cfg["promo_price"],
                promo_period_months=cfg["promo_months"],
                promo_end_date=None,
                contract_length=cfg["contract"],
                billing_cycle_days=cfg["billing_cycle_days"],
                data_allowance_gb=cfg["data_gb"],
                is_unlimited_data=False,
                network="Vodafone",
                network_tech="5G",
                deal_channel="affiliate",
                deal_channel_label="Lyca Partner Link",
                direct_url=cfg["url"],
                source_url=affiliate_url,
                scraped_at=scraped_at,
            )
        )

    return plans
