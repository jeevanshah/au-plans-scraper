"""Telco Bundles comparison engine.

Models bundle discounts across Australian telcos when pairing NBN broadband
with Mobile SIMs, Energy plans, or Banking perks. Outputs structured bundle
records conforming to the Bundles front-end schema.
"""
from __future__ import annotations

import re
from typing import Literal
from pydantic import BaseModel, Field


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
            )
        )

    # 2. Superloop: $5/mo with 1 SIM, $10/mo with 2 SIMs, $15/mo with 3+ SIMs
    sloop_nbn = nbn_by_provider.get("Superloop", [])
    sim_options = [
        ("1x 25GB Mobile SIM", 20.0, 5.0, "1sim"),
        ("2x 25GB Mobile SIMs", 40.0, 10.0, "2sims"),
        ("3x 25GB Mobile SIMs", 60.0, 15.0, "3sims"),
    ]
    for nbn in sloop_nbn:
        tier_label = _normalize_tier(nbn.get("tier", "NBN 50"))
        speed_label = _broadband_speed(nbn.get("tier", "50/20"))
        for s_name, s_price, s_discount, s_slug in sim_options:
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
                )
            )

    # 3. TPG: $5/mo discount when bundling NBN with TPG Mobile SIM
    tpg_nbn = nbn_by_provider.get("TPG", [])
    tpg_mob = mobile_by_provider.get("TPG", [])
    tpg_sim = next((m for m in tpg_mob if "25GB" in m.get("tier", "")), None)
    tpg_sim_reg = tpg_sim.get("regularPrice", 25.0) if tpg_sim else 25.0
    tpg_sim_name = "25GB Mobile SIM"

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
            )
        )

    # 4. Vodafone: Bundle & Save $5/mo on NBN when paired with active postpaid mobile plan
    voda_nbn = nbn_by_provider.get("Vodafone", [])
    voda_mob = mobile_by_provider.get("Vodafone", [])
    voda_sim = next((m for m in voda_mob if "65GB" in m.get("tier", "")), None)
    voda_sim_reg = voda_sim.get("regularPrice", 45.0) if voda_sim else 45.0
    voda_sim_name = "65GB Postpaid SIM"

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
            )
        )

    # 5. MATE: $10/mo ongoing discount on broadband when bundled with any MATE mobile service
    mate_nbn = nbn_by_provider.get("Mate", [])
    mate_mob = mobile_by_provider.get("Mate", [])
    mate_sim = next((m for m in mate_mob if "15GB" in m.get("tier", "")), None)
    mate_sim_reg = mate_sim.get("regularPrice", 30.0) if mate_sim else 30.0
    mate_sim_name = "Good Mates 15GB SIM"

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
            )
        )

    # 6. SpinTel: $3 to $5/mo discount on mobile SIM when active with SpinTel broadband
    spintel_nbn = nbn_by_provider.get("SpinTel", [])
    spintel_sim_name = "22GB 5G SIM"
    spintel_sim_reg = 14.0
    spintel_discount = 4.0  # $4/mo discount in the $3-$5 range

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
            )
        )

    # 7. Dodo: $5/mo broadband discount with 1 energy service, or $10/mo when bundling Electricity + Gas
    dodo_nbn = nbn_by_provider.get("Dodo", [])
    dodo_energy_options = [
        ("Dodo Electricity", 5.0, "electricity"),
        ("Dodo Electricity & Gas", 10.0, "dual-energy"),
    ]
    for nbn in dodo_nbn:
        tier_label = _normalize_tier(nbn.get("tier", "NBN 50"))
        speed_label = _broadband_speed(nbn.get("tier", "50/20"))
        for e_name, e_discount, e_slug in dodo_energy_options:
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
            )
        )

    # 9. amaysim: $10/mo ongoing discount on NBN when bundled with active amaysim mobile SIM plan
    amay_nbn = nbn_by_provider.get("amaysim", [])
    amay_mob = mobile_by_provider.get("amaysim", [])
    amay_sim = next((m for m in amay_mob if "15GB" in m.get("tier", "")), None)
    amay_sim_reg = amay_sim.get("regularPrice", 15.0) if amay_sim else 15.0
    amay_sim_name = "15GB Mobile SIM"

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
            )
        )

    # 10. More Telecom: $25/mo off for Commonwealth Bank (CBA) customers
    more_nbn = nbn_by_provider.get("More Telecom", [])
    more_cba_perk = "Commonwealth Bank Customer Perk"
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
            )
        )

    # 11. iiNet: $5/mo bundling discount on mobile SIM when linked with iiNet broadband
    iinet_nbn = nbn_by_provider.get("iiNet", [])
    iinet_sim_name = "50GB Mobile SIM"
    iinet_sim_reg = 25.0
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
            )
        )

    # 12. Exetel: Slash My Bill $5/mo (1 service), $7.50/mo (2 services), $10/mo (3 services)
    exetel_nbn = nbn_by_provider.get("Exetel", [])
    exetel_options = [
        ("1x Exetel Mobile SIM", 20.0, 5.0, "1sim"),
        ("2x Exetel Mobile SIMs", 40.0, 7.50, "2sims"),
        ("3x Exetel Mobile SIMs", 60.0, 10.0, "3sims"),
    ]
    for nbn in exetel_nbn:
        tier_label = _normalize_tier(nbn.get("tier", "NBN 500"))
        speed_label = _broadband_speed(nbn.get("tier", "500/50"))
        for s_name, s_price, s_discount, s_slug in exetel_options:
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
                )
            )

    # 13. Optus: Multi-service bundle: $5/mo off when pairing Optus NBN with Optus Mobile
    optus_nbn = nbn_by_provider.get("Optus", [])
    optus_sim_name = "50GB Mobile SIM"
    optus_sim_reg = 45.0
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
            )
        )

    # 14. Flip: $5/mo discount on mobile plan when paired with active Flip NBN
    flip_nbn = nbn_by_provider.get("Flip", [])
    flip_sim_name = "20GB Mobile SIM"
    flip_sim_reg = 15.0
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
