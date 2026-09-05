"""Telco Bundles comparison engine.

Models bundle discounts across Australian telcos when pairing NBN broadband
with Mobile SIMs, Energy plans, or Banking perks. Outputs structured bundle
records conforming to the exact jrsdigital-site front-end schema.
"""
from __future__ import annotations

import re
from typing import Literal
from pydantic import BaseModel, Field


class BundleRuleInfo(BaseModel):
    hasBundle: bool = True
    type: Literal["mobile", "energy", "bank_perk"]
    discountMonthly: float = Field(gt=0)
    shortLabel: str
    label: str
    description: str
    howToGet: str
    realityCheck: str
    cisUrl: str


class BundleDeal(BaseModel):
    id: str
    provider: str
    title: str
    tier: str
    serviceType: Literal["bundle"] = "bundle"
    broadbandName: str
    broadbandSpeed: str
    secondaryName: str
    secondaryType: Literal["mobile", "energy", "bank_perk"]
    promoPrice: float = Field(gt=0)
    regularPrice: float = Field(gt=0)
    promoMonths: int | None = Field(default=None, gt=0)
    totalFirstYear: float = Field(gt=0)
    totalSixMonth: float = Field(gt=0)
    annualSavings: float = Field(ge=0)
    discountMonthly: float = Field(gt=0)
    url: str
    bundleRule: BundleRuleInfo


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _normalize_tier(tier: str) -> str:
    """Normalize speed tier to standard format e.g. 'NBN 50/20' -> 'NBN 50'."""
    m = re.search(r"NBN\s*(\d+)", tier, re.IGNORECASE)
    if m:
        return f"NBN {m.group(1)}"
    return tier


def _broadband_speed(tier: str) -> str:
    """Extract standard speed representation e.g. 'NBN 50/20' -> '50/20 Mbps'."""
    m = re.search(r"(\d+(?:/\d+)?)", tier)
    if m:
        return f"{m.group(1)} Mbps"
    return tier


def _calc_totals(
    bb_reg: float,
    bb_promo: float | None,
    bb_promo_months: int | None,
    sec_reg: float,
    discount_monthly: float,
    bundle_discount_months: int | None = None,
) -> tuple[float, float, int | None, float, float, float]:
    """Calculate (regular_price, promo_price, promo_months, total_1yr, total_6mo, annual_savings)."""
    regular_price = round(bb_reg + sec_reg, 2)
    ongoing_monthly = round(regular_price - discount_monthly, 2)

    has_bb_promo = bb_promo is not None and bb_promo_months is not None and bb_promo < bb_reg

    if has_bb_promo:
        promo_months = bb_promo_months
        promo_price = round(bb_promo + sec_reg - discount_monthly, 2)
    else:
        promo_months = bundle_discount_months if bundle_discount_months is not None else 12
        promo_price = ongoing_monthly

    m = min(12, promo_months) if promo_months else 0
    total_1yr = round((m * promo_price) + ((12 - m) * ongoing_monthly), 2)
    m6 = min(6, promo_months) if promo_months else 0
    total_6mo = round((m6 * promo_price) + ((6 - m6) * ongoing_monthly), 2)
    annual_savings = round(discount_monthly * 12, 2)

    return regular_price, promo_price, promo_months, total_1yr, total_6mo, annual_savings


def generate_bundles(all_deals: list[dict], month_key: str | None = None) -> list[dict]:
    """Generate bundle comparison deals from scraped deal records."""
    bundles: list[BundleDeal] = []

    # Filter available NBN deals
    nbn_by_provider: dict[str, list[dict]] = {}
    mobile_by_provider: dict[str, list[dict]] = {}

    for deal in all_deals:
        provider = deal.get("provider", "")
        service_type = deal.get("serviceType", "")
        if service_type == "nbn":
            nbn_by_provider.setdefault(provider, []).append(deal)
        elif service_type == "mobile":
            mobile_by_provider.setdefault(provider, []).append(deal)

    # 1. Aussie Broadband: $5/mo off NBN per active mobile SIM
    abb_nbn = nbn_by_provider.get("Aussie Broadband", [])
    abb_mob = mobile_by_provider.get("Aussie Broadband", [])
    abb_sim = next((m for m in abb_mob if "20GB" in m.get("tier", "")), None)
    sim_reg = abb_sim.get("regularPrice", 30.0) if abb_sim else 30.0
    sim_name = "20GB 5G SIM"
    abb_rule = BundleRuleInfo(
        hasBundle=True,
        type="mobile",
        discountMonthly=5.0,
        shortLabel="Save $5/mo with Mobile",
        label="Save $5/mo bundled with Aussie Broadband SIM",
        description="Save $5/mo off broadband when maintaining an active eligible mobile SIM on the same account.",
        howToGet="Add an eligible mobile SIM to your broadband account at checkout.",
        realityCheck="Verify that Aussie BB's $15–$25/mo mobile SIM matches your data needs vs using a standalone budget MVNO.",
        cisUrl="https://www.aussiebroadband.com.au/legal/",
    )

    for nbn in abb_nbn:
        tier_label = _normalize_tier(nbn.get("tier", "NBN 50"))
        speed_label = _broadband_speed(nbn.get("tier", "50/20"))
        reg_p, promo_p, promo_m, t1y, t6m, sav = _calc_totals(
            bb_reg=nbn.get("regularPrice", 85.0),
            bb_promo=nbn.get("promoPrice"),
            bb_promo_months=nbn.get("promoMonths"),
            sec_reg=sim_reg,
            discount_monthly=5.0,
        )
        b_id = f"bundle-aussie-broadband-{_slugify(tier_label)}-{_slugify(sim_name)}"
        bundles.append(
            BundleDeal(
                id=b_id,
                provider="Aussie Broadband",
                title=f"{tier_label} + {sim_name}",
                tier=tier_label,
                broadbandName=nbn.get("title", f"{tier_label} Unlimited"),
                broadbandSpeed=speed_label,
                secondaryName=sim_name,
                secondaryType="mobile",
                promoPrice=promo_p,
                regularPrice=reg_p,
                promoMonths=promo_m,
                totalFirstYear=t1y,
                totalSixMonth=t6m,
                annualSavings=sav,
                discountMonthly=5.0,
                url=nbn.get("url", "https://www.aussiebroadband.com.au/nbn-plans/"),
                bundleRule=abb_rule,
            )
        )

    # 2. Superloop: $5/mo with 1 SIM, $10/mo with 2 SIMs, $15/mo with 3+ SIMs
    sloop_nbn = nbn_by_provider.get("Superloop", [])
    sim_options = [
        (
            "1x 25GB Mobile SIM",
            20.0,
            5.0,
            "1sim",
            BundleRuleInfo(
                hasBundle=True,
                type="mobile",
                discountMonthly=5.0,
                shortLabel="Save $5/mo with 1 SIM",
                label="Save $5/mo with Superloop Mobile SIM",
                description="Get $5/mo off your broadband bill when maintaining 1 active Superloop mobile SIM plan on the same account.",
                howToGet="Add a Superloop SIM plan to your account to automatically trigger monthly bill credits.",
                realityCheck="Superloop mobile operates on the Telstra wholesale network; check your local coverage.",
                cisUrl="https://www.superloop.com/legal/critical-information-summaries",
            ),
        ),
        (
            "2x 25GB Mobile SIMs",
            40.0,
            10.0,
            "2sims",
            BundleRuleInfo(
                hasBundle=True,
                type="mobile",
                discountMonthly=10.0,
                shortLabel="Save $10/mo with 2 SIMs",
                label="Save $10/mo with 2x Superloop Mobile SIMs",
                description="Get $10/mo off your broadband bill when maintaining 2 active Superloop mobile SIM plans on the same account.",
                howToGet="Add 2 Superloop SIM plans to your account to automatically trigger tier-2 monthly bill credits.",
                realityCheck="Superloop mobile operates on the Telstra wholesale network; check your local coverage.",
                cisUrl="https://www.superloop.com/legal/critical-information-summaries",
            ),
        ),
        (
            "3x 25GB Mobile SIMs",
            60.0,
            15.0,
            "3sims",
            BundleRuleInfo(
                hasBundle=True,
                type="mobile",
                discountMonthly=15.0,
                shortLabel="Save $15/mo with 3 SIMs",
                label="Save $15/mo with 3+ Superloop Mobile SIMs",
                description="Get $15/mo off your broadband bill when maintaining 3 or more active Superloop mobile SIM plans on the same account.",
                howToGet="Add 3+ Superloop SIM plans to your account to automatically trigger tier-3 monthly bill credits.",
                realityCheck="Compare total family mobile spend against standalone multi-SIM discounts.",
                cisUrl="https://www.superloop.com/legal/critical-information-summaries",
            ),
        ),
    ]
    for nbn in sloop_nbn:
        tier_label = _normalize_tier(nbn.get("tier", "NBN 50"))
        speed_label = _broadband_speed(nbn.get("tier", "50/20"))
        for s_name, s_price, s_discount, s_slug, s_rule in sim_options:
            reg_p, promo_p, promo_m, t1y, t6m, sav = _calc_totals(
                bb_reg=nbn.get("regularPrice", 79.0),
                bb_promo=nbn.get("promoPrice"),
                bb_promo_months=nbn.get("promoMonths"),
                sec_reg=s_price,
                discount_monthly=s_discount,
            )
            b_id = f"bundle-superloop-{_slugify(tier_label)}-{s_slug}"
            bundles.append(
                BundleDeal(
                    id=b_id,
                    provider="Superloop",
                    title=f"{tier_label} + {s_name}",
                    tier=tier_label,
                    broadbandName=nbn.get("title", f"{tier_label} Plan"),
                    broadbandSpeed=speed_label,
                    secondaryName=s_name,
                    secondaryType="mobile",
                    promoPrice=promo_p,
                    regularPrice=reg_p,
                    promoMonths=promo_m,
                    totalFirstYear=t1y,
                    totalSixMonth=t6m,
                    annualSavings=sav,
                    discountMonthly=s_discount,
                    url=nbn.get("url", "https://www.superloop.com/internet/nbn/"),
                    bundleRule=s_rule,
                )
            )

    # 3. TPG: $5/mo discount when bundling NBN with TPG Mobile SIM
    tpg_nbn = nbn_by_provider.get("TPG", [])
    tpg_mob = mobile_by_provider.get("TPG", [])
    tpg_sim = next((m for m in tpg_mob if "25GB" in m.get("tier", "")), None)
    tpg_sim_reg = tpg_sim.get("regularPrice", 25.0) if tpg_sim else 25.0
    tpg_sim_name = "25GB Mobile SIM"
    tpg_rule = BundleRuleInfo(
        hasBundle=True,
        type="mobile",
        discountMonthly=5.0,
        shortLabel="Save $5/mo with Mobile",
        label="Save $5/mo bundled with TPG Mobile SIM",
        description="Save $5/mo when bundling an eligible TPG NBN plan with a TPG Mobile plan on the same billing account.",
        howToGet="Link your TPG Mobile service with your TPG NBN account in My Account.",
        realityCheck="TPG mobile operates on the Vodafone 4G/5G mobile network; ensure coverage suits your daily locations.",
        cisUrl="https://www.tpg.com.au/terms-and-conditions",
    )

    for nbn in tpg_nbn:
        tier_label = _normalize_tier(nbn.get("tier", "NBN 50"))
        speed_label = _broadband_speed(nbn.get("tier", "50/20"))
        reg_p, promo_p, promo_m, t1y, t6m, sav = _calc_totals(
            bb_reg=nbn.get("regularPrice", 84.99),
            bb_promo=nbn.get("promoPrice"),
            bb_promo_months=nbn.get("promoMonths"),
            sec_reg=tpg_sim_reg,
            discount_monthly=5.0,
        )
        b_id = f"bundle-tpg-{_slugify(tier_label)}-{_slugify(tpg_sim_name)}"
        bundles.append(
            BundleDeal(
                id=b_id,
                provider="TPG",
                title=f"{tier_label} + {tpg_sim_name}",
                tier=tier_label,
                broadbandName=nbn.get("title", f"{tier_label} Plan"),
                broadbandSpeed=speed_label,
                secondaryName=tpg_sim_name,
                secondaryType="mobile",
                promoPrice=promo_p,
                regularPrice=reg_p,
                promoMonths=promo_m,
                totalFirstYear=t1y,
                totalSixMonth=t6m,
                annualSavings=sav,
                discountMonthly=5.0,
                url=nbn.get("url", "https://www.tpg.com.au/nbn"),
                bundleRule=tpg_rule,
            )
        )

    # 4. Vodafone: Bundle & Save $5/mo on NBN when paired with active postpaid mobile plan
    voda_nbn = nbn_by_provider.get("Vodafone", [])
    voda_mob = mobile_by_provider.get("Vodafone", [])
    voda_sim = next((m for m in voda_mob if "65GB" in m.get("tier", "")), None)
    voda_sim_reg = voda_sim.get("regularPrice", 45.0) if voda_sim else 45.0
    voda_sim_name = "65GB Postpaid SIM"
    voda_rule = BundleRuleInfo(
        hasBundle=True,
        type="mobile",
        discountMonthly=5.0,
        shortLabel="Bundle & Save $5/mo",
        label="Bundle & Save $5/mo on NBN with Postpaid Mobile",
        description="Save $5/mo off your NBN plan when combined under the same account with an active Vodafone postpaid mobile service.",
        howToGet="Link your NBN service to your existing Vodafone postpaid mobile billing account.",
        realityCheck="Vodafone Bundle & Save requires active postpaid mobile; prepaid services are excluded.",
        cisUrl="https://www.vodafone.com.au/critical-information-summaries",
    )

    for nbn in voda_nbn:
        tier_label = _normalize_tier(nbn.get("tier", "NBN 50"))
        speed_label = _broadband_speed(nbn.get("tier", "50/20"))
        reg_p, promo_p, promo_m, t1y, t6m, sav = _calc_totals(
            bb_reg=nbn.get("regularPrice", 85.0),
            bb_promo=nbn.get("promoPrice"),
            bb_promo_months=nbn.get("promoMonths"),
            sec_reg=voda_sim_reg,
            discount_monthly=5.0,
        )
        b_id = f"bundle-vodafone-{_slugify(tier_label)}-{_slugify(voda_sim_name)}"
        bundles.append(
            BundleDeal(
                id=b_id,
                provider="Vodafone",
                title=f"{tier_label} + {voda_sim_name}",
                tier=tier_label,
                broadbandName=nbn.get("title", f"{tier_label} Plan"),
                broadbandSpeed=speed_label,
                secondaryName=voda_sim_name,
                secondaryType="mobile",
                promoPrice=promo_p,
                regularPrice=reg_p,
                promoMonths=promo_m,
                totalFirstYear=t1y,
                totalSixMonth=t6m,
                annualSavings=sav,
                discountMonthly=5.0,
                url=nbn.get("url", "https://www.vodafone.com.au/home-internet/nbn"),
                bundleRule=voda_rule,
            )
        )

    # 5. MATE: $10/mo ongoing discount on broadband when bundled with any MATE mobile service
    mate_nbn = nbn_by_provider.get("Mate", [])
    mate_mob = mobile_by_provider.get("Mate", [])
    mate_sim = next((m for m in mate_mob if "15GB" in m.get("tier", "")), None)
    mate_sim_reg = mate_sim.get("regularPrice", 30.0) if mate_sim else 30.0
    mate_sim_name = "Good Mates 15GB SIM"
    mate_rule = BundleRuleInfo(
        hasBundle=True,
        type="mobile",
        discountMonthly=10.0,
        shortLabel="Save $10/mo with Mobile",
        label="Save $10/mo ongoing with MATE Mobile SIM",
        description="Enjoy an ongoing $10/mo discount on your broadband service as long as you have an active MATE mobile service on the same account.",
        howToGet="Add any MATE mobile SIM to your account; the $10/mo discount applies automatically to your broadband bill.",
        realityCheck="MATE mobile runs on Telstra wholesale with uncapped speeds; verify if 15GB–60GB allowances match your monthly usage.",
        cisUrl="https://www.letsbemates.com.au/terms/",
    )

    for nbn in mate_nbn:
        tier_label = _normalize_tier(nbn.get("tier", "NBN 50"))
        speed_label = _broadband_speed(nbn.get("tier", "50/20"))
        reg_p, promo_p, promo_m, t1y, t6m, sav = _calc_totals(
            bb_reg=nbn.get("regularPrice", 85.0),
            bb_promo=nbn.get("promoPrice"),
            bb_promo_months=nbn.get("promoMonths"),
            sec_reg=mate_sim_reg,
            discount_monthly=10.0,
        )
        b_id = f"bundle-mate-{_slugify(tier_label)}-{_slugify(mate_sim_name)}"
        bundles.append(
            BundleDeal(
                id=b_id,
                provider="Mate",
                title=f"{tier_label} + {mate_sim_name}",
                tier=tier_label,
                broadbandName=nbn.get("title", f"{tier_label} Plan"),
                broadbandSpeed=speed_label,
                secondaryName=mate_sim_name,
                secondaryType="mobile",
                promoPrice=promo_p,
                regularPrice=reg_p,
                promoMonths=promo_m,
                totalFirstYear=t1y,
                totalSixMonth=t6m,
                annualSavings=sav,
                discountMonthly=10.0,
                url=nbn.get("url", "https://www.letsbemates.com.au/nbn/"),
                bundleRule=mate_rule,
            )
        )

    # 6. SpinTel: $3 to $5/mo discount on mobile SIM when active with SpinTel broadband
    spintel_nbn = nbn_by_provider.get("SpinTel", [])
    spintel_sim_name = "22GB 5G SIM"
    spintel_sim_reg = 14.0
    spintel_discount = 4.0  # $4/mo discount in the $3-$5 range
    spintel_rule = BundleRuleInfo(
        hasBundle=True,
        type="mobile",
        discountMonthly=spintel_discount,
        shortLabel="Save $4/mo on Mobile",
        label="Save $3–$5/mo on Mobile SIM when active with Broadband",
        description="Get a recurring $4/mo discount on your SpinTel mobile SIM service when maintained alongside an active SpinTel broadband connection.",
        howToGet="Select the broadband bundle discount option when ordering your SpinTel SIM in the customer portal.",
        realityCheck="Discount applies directly to the mobile service charge on your combined monthly bill.",
        cisUrl="https://www.spintel.net.au/critical-information-summaries",
    )

    for nbn in spintel_nbn:
        tier_label = _normalize_tier(nbn.get("tier", "NBN 50"))
        speed_label = _broadband_speed(nbn.get("tier", "50/20"))
        reg_p, promo_p, promo_m, t1y, t6m, sav = _calc_totals(
            bb_reg=nbn.get("regularPrice", 74.95),
            bb_promo=nbn.get("promoPrice"),
            bb_promo_months=nbn.get("promoMonths"),
            sec_reg=spintel_sim_reg,
            discount_monthly=spintel_discount,
        )
        b_id = f"bundle-spintel-{_slugify(tier_label)}-{_slugify(spintel_sim_name)}"
        bundles.append(
            BundleDeal(
                id=b_id,
                provider="SpinTel",
                title=f"{tier_label} + {spintel_sim_name}",
                tier=tier_label,
                broadbandName=nbn.get("title", f"{tier_label} Plan"),
                broadbandSpeed=speed_label,
                secondaryName=spintel_sim_name,
                secondaryType="mobile",
                promoPrice=promo_p,
                regularPrice=reg_p,
                promoMonths=promo_m,
                totalFirstYear=t1y,
                totalSixMonth=t6m,
                annualSavings=sav,
                discountMonthly=spintel_discount,
                url=nbn.get("url", "https://www.spintel.net.au/lp/home/nbn-wo"),
                bundleRule=spintel_rule,
            )
        )

    # 7. Dodo: $5/mo broadband discount with 1 energy service, or $10/mo when bundling Electricity + Gas
    dodo_nbn = nbn_by_provider.get("Dodo", [])
    dodo_energy_options = [
        (
            "Dodo Electricity",
            5.0,
            "electricity",
            BundleRuleInfo(
                hasBundle=True,
                type="energy",
                discountMonthly=5.0,
                shortLabel="Save $5/mo with Electricity",
                label="Save $5/mo on Broadband with Dodo Electricity",
                description="Save $5/mo off your Dodo broadband bill when bundling with an active Dodo Electricity service at the same address.",
                howToGet="Sign up for Dodo Electricity using the same account and residential address as your Dodo broadband.",
                realityCheck="Compare Dodo's underlying electricity kWh supply and usage rates against the default market offer (DMO/VDO).",
                cisUrl="https://www.dodo.com/regulatory/critical-information-summaries",
            ),
        ),
        (
            "Dodo Electricity & Gas",
            10.0,
            "dual-energy",
            BundleRuleInfo(
                hasBundle=True,
                type="energy",
                discountMonthly=10.0,
                shortLabel="Save $10/mo with Dual Fuel",
                label="Save $10/mo on Broadband with Electricity & Gas",
                description="Save $10/mo off your Dodo broadband bill when bundling with both Dodo Electricity and Natural Gas at the same address.",
                howToGet="Sign up for both Dodo Electricity and Gas on the same account and address as your Dodo broadband.",
                realityCheck="Compare dual-fuel utility rates against regional benchmarks to ensure net savings.",
                cisUrl="https://www.dodo.com/regulatory/critical-information-summaries",
            ),
        ),
    ]
    for nbn in dodo_nbn:
        tier_label = _normalize_tier(nbn.get("tier", "NBN 50"))
        speed_label = _broadband_speed(nbn.get("tier", "50/20"))
        for e_name, e_discount, e_slug, e_rule in dodo_energy_options:
            reg_p, promo_p, promo_m, t1y, t6m, sav = _calc_totals(
                bb_reg=nbn.get("regularPrice", 75.0),
                bb_promo=nbn.get("promoPrice"),
                bb_promo_months=nbn.get("promoMonths"),
                sec_reg=0.0,  # Energy usage billed on state utility tariffs separately
                discount_monthly=e_discount,
            )
            b_id = f"bundle-dodo-{_slugify(tier_label)}-{e_slug}"
            bundles.append(
                BundleDeal(
                    id=b_id,
                    provider="Dodo",
                    title=f"{tier_label} + {e_name}",
                    tier=tier_label,
                    broadbandName=nbn.get("title", f"{tier_label} Plan"),
                    broadbandSpeed=speed_label,
                    secondaryName=e_name,
                    secondaryType="energy",
                    promoPrice=promo_p,
                    regularPrice=reg_p,
                    promoMonths=promo_m,
                    totalFirstYear=t1y,
                    totalSixMonth=t6m,
                    annualSavings=sav,
                    discountMonthly=e_discount,
                    url=nbn.get("url", "https://www.dodo.com/nbn"),
                    bundleRule=e_rule,
                )
            )

    # 8. Tangerine: 30% off NBN for 12 months for Commonwealth Bank (CBA) customers
    tang_nbn = nbn_by_provider.get("Tangerine", [])
    cba_perk_name = "Commonwealth Bank Customer Perk"
    for nbn in tang_nbn:
        tier_label = _normalize_tier(nbn.get("tier", "NBN 50"))
        speed_label = _broadband_speed(nbn.get("tier", "50/20"))
        bb_reg = nbn.get("regularPrice", 80.0)
        cba_discount_monthly = round(bb_reg * 0.30, 2)
        reg_p, promo_p, promo_m, t1y, t6m, sav = _calc_totals(
            bb_reg=bb_reg,
            bb_promo=None,
            bb_promo_months=None,
            sec_reg=0.0,
            discount_monthly=cba_discount_monthly,
            bundle_discount_months=12,
        )
        tang_rule = BundleRuleInfo(
            hasBundle=True,
            type="bank_perk",
            discountMonthly=cba_discount_monthly,
            shortLabel="30% Off for CBA Customers",
            label="30% off NBN for 12 months for CommBank Customers",
            description="Commonwealth Bank (CBA) customers receive an exclusive 30% discount on Tangerine NBN plans for the first 12 months.",
            howToGet="Sign up via the CommBank app Yello perks section or pay your Tangerine bill using an eligible CommBank card.",
            realityCheck="After month 12, the discount ends and reverts to Tangerine's standard in-market rate; set a calendar reminder to review.",
            cisUrl="https://www.tangerinetelecom.com.au/critical-information-summaries",
        )
        b_id = f"bundle-tangerine-{_slugify(tier_label)}-cba-perk"
        bundles.append(
            BundleDeal(
                id=b_id,
                provider="Tangerine",
                title=f"{tier_label} + CBA 30% Off Perk",
                tier=tier_label,
                broadbandName=nbn.get("title", f"{tier_label} Plan"),
                broadbandSpeed=speed_label,
                secondaryName=cba_perk_name,
                secondaryType="bank_perk",
                promoPrice=promo_p,
                regularPrice=reg_p,
                promoMonths=promo_m,
                totalFirstYear=t1y,
                totalSixMonth=t6m,
                annualSavings=sav,
                discountMonthly=cba_discount_monthly,
                url=nbn.get("url", "https://www.tangerinetelecom.com.au/nbn/nbn-broadband"),
                bundleRule=tang_rule,
            )
        )

    # 9. amaysim: $10/mo ongoing discount on NBN when bundled with active amaysim mobile SIM plan
    amay_nbn = nbn_by_provider.get("amaysim", [])
    amay_mob = mobile_by_provider.get("amaysim", [])
    amay_sim = next((m for m in amay_mob if "15GB" in m.get("tier", "")), None)
    amay_sim_reg = amay_sim.get("regularPrice", 15.0) if amay_sim else 15.0
    amay_sim_name = "15GB Mobile SIM"
    amay_rule = BundleRuleInfo(
        hasBundle=True,
        type="mobile",
        discountMonthly=10.0,
        shortLabel="Save $10/mo with SIM",
        label="Save $10/mo ongoing on NBN with active amaysim SIM",
        description="Save $10/mo ongoing on your amaysim NBN plan after intro offers for as long as you maintain an active amaysim mobile SIM plan.",
        howToGet="Sign up for amaysim NBN using the same amaysim account as your active mobile SIM service.",
        realityCheck="Even amaysim's cheapest $15/28-day SIM qualifies you for the $10/mo NBN discount, yielding net $5/mo SIM cost.",
        cisUrl="https://www.amaysim.com.au/terms-conditions",
    )

    for nbn in amay_nbn:
        tier_label = _normalize_tier(nbn.get("tier", "NBN 50"))
        speed_label = _broadband_speed(nbn.get("tier", "50/20"))
        reg_p, promo_p, promo_m, t1y, t6m, sav = _calc_totals(
            bb_reg=nbn.get("regularPrice", 80.0),
            bb_promo=nbn.get("promoPrice"),
            bb_promo_months=nbn.get("promoMonths"),
            sec_reg=amay_sim_reg,
            discount_monthly=10.0,
        )
        b_id = f"bundle-amaysim-{_slugify(tier_label)}-{_slugify(amay_sim_name)}"
        bundles.append(
            BundleDeal(
                id=b_id,
                provider="amaysim",
                title=f"{tier_label} + {amay_sim_name}",
                tier=tier_label,
                broadbandName=nbn.get("title", f"{tier_label} Plan"),
                broadbandSpeed=speed_label,
                secondaryName=amay_sim_name,
                secondaryType="mobile",
                promoPrice=promo_p,
                regularPrice=reg_p,
                promoMonths=promo_m,
                totalFirstYear=t1y,
                totalSixMonth=t6m,
                annualSavings=sav,
                discountMonthly=10.0,
                url=nbn.get("url", "https://www.amaysim.com.au/nbn"),
                bundleRule=amay_rule,
            )
        )

    # 10. More Telecom: $25/mo off for Commonwealth Bank (CBA) customers
    more_nbn = nbn_by_provider.get("More Telecom", [])
    more_cba_perk = "Commonwealth Bank Customer Perk"
    more_rule = BundleRuleInfo(
        hasBundle=True,
        type="bank_perk",
        discountMonthly=25.0,
        shortLabel="Save $25/mo for CBA Customers",
        label="Save $25/mo off NBN for CommBank Customers",
        description="CommBank customers enjoy an exclusive $25/mo discount off More Telecom NBN plans for the first 36 months, reverting to $10/mo ongoing.",
        howToGet="Link your CommBank credit or debit card as your recurring payment method during More Telecom NBN sign-up.",
        realityCheck="Requires paying with a CommBank card; reverting to non-CommBank payment forfeits the $25/mo discount.",
        cisUrl="https://www.more.com.au/about/critical-information-summaries",
    )
    for nbn in more_nbn:
        tier_label = _normalize_tier(nbn.get("tier", "NBN 50"))
        speed_label = _broadband_speed(nbn.get("tier", "50/20"))
        bb_reg = nbn.get("regularPrice", 80.0)
        more_discount = 25.0
        reg_p, promo_p, promo_m, t1y, t6m, sav = _calc_totals(
            bb_reg=bb_reg,
            bb_promo=None,
            bb_promo_months=None,
            sec_reg=0.0,
            discount_monthly=more_discount,
            bundle_discount_months=12,
        )
        b_id = f"bundle-more-telecom-{_slugify(tier_label)}-cba-perk"
        bundles.append(
            BundleDeal(
                id=b_id,
                provider="More Telecom",
                title=f"{tier_label} + CBA $25 Off Perk",
                tier=tier_label,
                broadbandName=nbn.get("title", f"{tier_label} Plan"),
                broadbandSpeed=speed_label,
                secondaryName=more_cba_perk,
                secondaryType="bank_perk",
                promoPrice=promo_p,
                regularPrice=reg_p,
                promoMonths=promo_m,
                totalFirstYear=t1y,
                totalSixMonth=t6m,
                annualSavings=sav,
                discountMonthly=more_discount,
                url=nbn.get("url", "https://www.more.com.au/personal/nbn-plans"),
                bundleRule=more_rule,
            )
        )

    # 11. iiNet: $5/mo bundling discount on mobile SIM when linked with iiNet broadband
    iinet_nbn = nbn_by_provider.get("iiNet", [])
    iinet_sim_name = "50GB Mobile SIM"
    iinet_sim_reg = 25.0
    iinet_rule = BundleRuleInfo(
        hasBundle=True,
        type="mobile",
        discountMonthly=5.0,
        shortLabel="Save $5/mo with Mobile",
        label="Save $5/mo on Mobile when linked with iiNet Internet",
        description="Receive a $5/mo bundling discount on eligible iiNet mobile SIM plans when linked to your active iiNet broadband account.",
        howToGet="Link your iiNet mobile plan to your internet account via the iiNet Toolbox dashboard.",
        realityCheck="Discount takes effect on the next billing cycle following successful account linking.",
        cisUrl="https://www.iinet.net.au/about/legal/cis/",
    )
    for nbn in iinet_nbn:
        tier_label = _normalize_tier(nbn.get("tier", "NBN 50"))
        speed_label = _broadband_speed(nbn.get("tier", "50/20"))
        reg_p, promo_p, promo_m, t1y, t6m, sav = _calc_totals(
            bb_reg=nbn.get("regularPrice", 84.99),
            bb_promo=nbn.get("promoPrice"),
            bb_promo_months=nbn.get("promoMonths"),
            sec_reg=iinet_sim_reg,
            discount_monthly=5.0,
        )
        b_id = f"bundle-iinet-{_slugify(tier_label)}-{_slugify(iinet_sim_name)}"
        bundles.append(
            BundleDeal(
                id=b_id,
                provider="iiNet",
                title=f"{tier_label} + {iinet_sim_name}",
                tier=tier_label,
                broadbandName=nbn.get("title", f"{tier_label} Plan"),
                broadbandSpeed=speed_label,
                secondaryName=iinet_sim_name,
                secondaryType="mobile",
                promoPrice=promo_p,
                regularPrice=reg_p,
                promoMonths=promo_m,
                totalFirstYear=t1y,
                totalSixMonth=t6m,
                annualSavings=sav,
                discountMonthly=5.0,
                url=nbn.get("url", "https://www.iinet.net.au/internet/broadband/nbn"),
                bundleRule=iinet_rule,
            )
        )

    # 12. Exetel: Slash My Bill $5/mo (1 service), $7.50/mo (2 services), $10/mo (3 services)
    exetel_nbn = nbn_by_provider.get("Exetel", [])
    exetel_options = [
        (
            "1x Exetel Mobile SIM",
            20.0,
            5.0,
            "1sim",
            BundleRuleInfo(
                hasBundle=True,
                type="mobile",
                discountMonthly=5.0,
                shortLabel="Save $5/mo with 1 SIM",
                label="Save $5/mo with Exetel Slash My Bill",
                description="Slash My Bill offers $5/mo off broadband with 1 mobile SIM plan active on the same account.",
                howToGet="Add an eligible Exetel mobile SIM service to your primary broadband account.",
                realityCheck="Exetel uses Telstra wholesale network; all services must share the identical residential account.",
                cisUrl="https://www.exetel.com.au/terms",
            ),
        ),
        (
            "2x Exetel Mobile SIMs",
            40.0,
            7.50,
            "2sims",
            BundleRuleInfo(
                hasBundle=True,
                type="mobile",
                discountMonthly=7.50,
                shortLabel="Save $7.50/mo with 2 SIMs",
                label="Save $7.50/mo with 2x Exetel Mobile SIMs",
                description="Slash My Bill offers $7.50/mo off broadband with 2 mobile SIM plans active on the same account.",
                howToGet="Add 2 eligible Exetel mobile SIM services to your primary broadband account.",
                realityCheck="Exetel uses Telstra wholesale network; all services must share the identical residential account.",
                cisUrl="https://www.exetel.com.au/terms",
            ),
        ),
        (
            "3x Exetel Mobile SIMs",
            60.0,
            10.0,
            "3sims",
            BundleRuleInfo(
                hasBundle=True,
                type="mobile",
                discountMonthly=10.0,
                shortLabel="Save $10/mo with 3 SIMs",
                label="Save $10/mo with 3+ Exetel Mobile SIMs",
                description="Slash My Bill offers $10/mo off broadband with 3 or more mobile SIM plans active on the same account.",
                howToGet="Add 3+ eligible Exetel mobile SIM services to your primary broadband account.",
                realityCheck="Exetel uses Telstra wholesale network; all services must share the identical residential account.",
                cisUrl="https://www.exetel.com.au/terms",
            ),
        ),
    ]
    for nbn in exetel_nbn:
        tier_label = _normalize_tier(nbn.get("tier", "NBN 500"))
        speed_label = _broadband_speed(nbn.get("tier", "500/50"))
        for s_name, s_price, s_discount, s_slug, s_rule in exetel_options:
            reg_p, promo_p, promo_m, t1y, t6m, sav = _calc_totals(
                bb_reg=nbn.get("regularPrice", 80.0),
                bb_promo=nbn.get("promoPrice"),
                bb_promo_months=nbn.get("promoMonths"),
                sec_reg=s_price,
                discount_monthly=s_discount,
            )
            b_id = f"bundle-exetel-{_slugify(tier_label)}-{s_slug}"
            bundles.append(
                BundleDeal(
                    id=b_id,
                    provider="Exetel",
                    title=f"{tier_label} + {s_name}",
                    tier=tier_label,
                    broadbandName=nbn.get("title", f"{tier_label} Plan"),
                    broadbandSpeed=speed_label,
                    secondaryName=s_name,
                    secondaryType="mobile",
                    promoPrice=promo_p,
                    regularPrice=reg_p,
                    promoMonths=promo_m,
                    totalFirstYear=t1y,
                    totalSixMonth=t6m,
                    annualSavings=sav,
                    discountMonthly=s_discount,
                    url=nbn.get("url", "https://www.exetel.com.au/broadband/nbn"),
                    bundleRule=s_rule,
                )
            )

    # 13. Optus: Multi-service bundle: $5/mo off when pairing Optus NBN with Optus Mobile
    optus_nbn = nbn_by_provider.get("Optus", [])
    optus_sim_name = "50GB Mobile SIM"
    optus_sim_reg = 45.0
    optus_rule = BundleRuleInfo(
        hasBundle=True,
        type="mobile",
        discountMonthly=5.0,
        shortLabel="Save $5/mo Multi-Service",
        label="Save $5/mo with Optus Multi-Service Discount",
        description="Save $5/mo off your account total when combining an eligible Optus home broadband plan with an Optus postpaid mobile plan.",
        howToGet="Ensure your Optus broadband and postpaid mobile services share the same My Account login and single monthly bill.",
        realityCheck="Both services must remain in active postpaid standing under the same account holder.",
        cisUrl="https://www.optus.com.au/about/legal/standard-forms-agreement",
    )
    for nbn in optus_nbn:
        tier_label = _normalize_tier(nbn.get("tier", "NBN 50"))
        speed_label = _broadband_speed(nbn.get("tier", "50/20"))
        reg_p, promo_p, promo_m, t1y, t6m, sav = _calc_totals(
            bb_reg=nbn.get("regularPrice", 89.0),
            bb_promo=nbn.get("promoPrice"),
            bb_promo_months=nbn.get("promoMonths"),
            sec_reg=optus_sim_reg,
            discount_monthly=5.0,
        )
        b_id = f"bundle-optus-{_slugify(tier_label)}-{_slugify(optus_sim_name)}"
        bundles.append(
            BundleDeal(
                id=b_id,
                provider="Optus",
                title=f"{tier_label} + {optus_sim_name}",
                tier=tier_label,
                broadbandName=nbn.get("title", f"{tier_label} Plan"),
                broadbandSpeed=speed_label,
                secondaryName=optus_sim_name,
                secondaryType="mobile",
                promoPrice=promo_p,
                regularPrice=reg_p,
                promoMonths=promo_m,
                totalFirstYear=t1y,
                totalSixMonth=t6m,
                annualSavings=sav,
                discountMonthly=5.0,
                url=nbn.get("url", "https://www.optus.com.au/broadband-nbn/home-broadband/plans"),
                bundleRule=optus_rule,
            )
        )

    # 14. Flip: $5/mo discount on mobile plan when paired with active Flip NBN
    flip_nbn = nbn_by_provider.get("Flip", [])
    flip_sim_name = "20GB Mobile SIM"
    flip_sim_reg = 15.0
    flip_rule = BundleRuleInfo(
        hasBundle=True,
        type="mobile",
        discountMonthly=5.0,
        shortLabel="Save $5/mo with Mobile",
        label="Save $5/mo on Mobile SIM bundled with Flip NBN",
        description="Receive a $5/mo discount on your companion Flip mobile plan when maintained with an active Flip NBN service.",
        howToGet="Order a companion Flip mobile SIM plan through the Flip customer portal under your existing NBN account.",
        realityCheck="Limited to eligible companion SIM tiers; check data allowance needs.",
        cisUrl="https://flipconnect.com.au/terms-and-conditions",
    )
    for nbn in flip_nbn:
        tier_label = _normalize_tier(nbn.get("tier", "NBN 50"))
        speed_label = _broadband_speed(nbn.get("tier", "50/20"))
        reg_p, promo_p, promo_m, t1y, t6m, sav = _calc_totals(
            bb_reg=nbn.get("regularPrice", 70.0),
            bb_promo=nbn.get("promoPrice"),
            bb_promo_months=nbn.get("promoMonths"),
            sec_reg=flip_sim_reg,
            discount_monthly=5.0,
        )
        b_id = f"bundle-flip-{_slugify(tier_label)}-{_slugify(flip_sim_name)}"
        bundles.append(
            BundleDeal(
                id=b_id,
                provider="Flip",
                title=f"{tier_label} + {flip_sim_name}",
                tier=tier_label,
                broadbandName=nbn.get("title", f"{tier_label} Plan"),
                broadbandSpeed=speed_label,
                secondaryName=flip_sim_name,
                secondaryType="mobile",
                promoPrice=promo_p,
                regularPrice=reg_p,
                promoMonths=promo_m,
                totalFirstYear=t1y,
                totalSixMonth=t6m,
                annualSavings=sav,
                discountMonthly=5.0,
                url=nbn.get("url", "https://flipconnect.com.au/nbn"),
                bundleRule=flip_rule,
            )
        )

    # Deduplicate bundles by ID just in case
    seen_ids: set[str] = set()
    unique_bundles: list[dict] = []
    for b in bundles:
        if b.id in seen_ids:
            continue
        seen_ids.add(b.id)
        unique_bundles.append(b.model_dump())

    return unique_bundles
