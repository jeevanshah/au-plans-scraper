"""Transform internal NbnPlan/MobilePlan models into the public deal-card JSON shape
consumed by the blog/app: camelCase fields, a marketing title/description, category,
and a single merged deals list across NBN and mobile."""
import re

from scraper.schema import MobilePlan, NbnPlan, SatellitePlan

CATEGORY = "Utilities"


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _make_id(provider: str, tier: str, scraped_at: str, extra: str | None = None) -> str:
    month_key = scraped_at[:7]  # YYYY-MM
    slug = f"{_slugify(provider)}-{_slugify(tier)}"
    if extra:
        extra_slug = _slugify(extra)
        if extra_slug and extra_slug not in slug:
            slug = f"{slug}-{extra_slug}"
    return f"{slug}-{month_key}"


def _source_note(provider: str, scraped_at: str) -> str:
    return f"{provider} official site, verified {scraped_at[:10]}"


def nbn_plan_to_deal(plan: NbnPlan) -> dict:
    has_promo = plan.promo_price is not None
    if has_promo:
        description = (
            f"{plan.speed_tier} plan discounted for the first {plan.promo_period_months} "
            f"months for new customers. Unlimited data, {plan.contract_length.lower()}."
        )
    else:
        description = f"{plan.speed_tier} plan. Unlimited data, {plan.contract_length.lower()}."

    if plan.plan_name.strip().lower() == plan.speed_tier.strip().lower() or plan.speed_tier.lower() in plan.plan_name.lower():
        title = plan.plan_name.strip()
    else:
        title = f"{plan.plan_name.strip()} {plan.speed_tier.strip()}"

    return {
        "id": _make_id(plan.provider, plan.speed_tier, plan.scraped_at, extra=plan.plan_name),
        "provider": plan.provider,
        "title": title,
        "category": CATEGORY,
        "description": description,
        "promoPrice": plan.promo_price if has_promo else plan.price_monthly,
        "regularPrice": plan.price_monthly,
        "promoMonths": plan.promo_period_months if has_promo else None,
        "validUntil": plan.promo_end_date,
        "url": plan.source_url,
        "serviceType": "nbn",
        "tier": plan.speed_tier,
        "typicalEveningSpeed": plan.typical_evening_speed_mbps,
        "techType": plan.tech_type,
        "postedAt": plan.scraped_at[:10],
        "_source": _source_note(plan.provider, plan.scraped_at),
    }


def mobile_plan_to_deal(plan: MobilePlan) -> dict:
    has_promo = plan.promo_price is not None
    data_desc = "Unlimited data" if plan.is_unlimited_data else f"{plan.data_allowance_gb:g}GB data"
    tier = "Unlimited" if plan.is_unlimited_data else f"{plan.data_allowance_gb:g}GB"

    if has_promo:
        description = (
            f"{data_desc} mobile plan discounted for the first {plan.promo_period_months} "
            f"months for new customers. {plan.contract_length}."
        )
    else:
        description = f"{data_desc} mobile plan. {plan.contract_length}."

    # Include contract_length in the id (but not the displayed `tier` field below) --
    # some providers (e.g. Boost) sell the same data allowance under different expiry
    # periods (28-day vs 186-day vs 365-day), which would otherwise collide on tier alone.
    id_key = f"{tier}-{plan.contract_length}"

    return {
        "id": _make_id(plan.provider, id_key, plan.scraped_at),
        "provider": plan.provider,
        "title": f"{plan.plan_name} {tier}",
        "category": CATEGORY,
        "description": description,
        "promoPrice": plan.promo_price if has_promo else plan.price_monthly,
        "regularPrice": plan.price_monthly,
        "promoMonths": plan.promo_period_months if has_promo else None,
        "validUntil": plan.promo_end_date,
        "url": plan.source_url,
        "serviceType": "mobile",
        "tier": tier,
        "techType": plan.network_tech,
        "billingCycleDays": plan.billing_cycle_days,
        "postedAt": plan.scraped_at[:10],
        "_source": _source_note(plan.provider, plan.scraped_at),
    }


def satellite_plan_to_deal(plan: SatellitePlan) -> dict:
    has_promo = plan.promo_price is not None
    data_desc = "Unlimited data" if plan.is_unlimited_data else f"{plan.data_allowance_gb:g}GB data"
    tier = f"{plan.network} {plan.plan_name}".strip()

    if has_promo:
        description = (
            f"{plan.network} satellite plan ({data_desc}) discounted for the first "
            f"{plan.promo_period_months} months for new customers. {plan.contract_length}."
        )
    else:
        description = f"{plan.network} satellite plan ({data_desc}). {plan.contract_length}."

    return {
        "id": _make_id(plan.provider, tier, plan.scraped_at),
        "provider": plan.provider,
        "title": f"{plan.plan_name} ({plan.network})",
        "category": CATEGORY,
        "description": description,
        "promoPrice": plan.promo_price if has_promo else plan.price_monthly,
        "regularPrice": plan.price_monthly,
        "promoMonths": plan.promo_period_months if has_promo else None,
        "validUntil": None,
        "url": plan.source_url,
        "serviceType": "satellite",
        "tier": tier,
        "techType": plan.network,
        "upfrontHardwareCost": plan.upfront_hardware_cost,
        "postedAt": plan.scraped_at[:10],
        "_source": _source_note(plan.provider, plan.scraped_at),
    }
