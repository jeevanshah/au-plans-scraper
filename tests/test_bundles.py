"""Unit tests for the Telco Bundles comparison engine."""
import json
from pathlib import Path
import pytest

from scraper.bundles import BundleDeal, generate_bundles

DEALS_FILE = Path(__file__).parent.parent / "data" / "deals.json"


@pytest.fixture
def deals_data():
    if not DEALS_FILE.exists():
        pytest.skip("data/deals.json not found")
    return json.loads(DEALS_FILE.read_text(encoding="utf-8"))


def test_bundle_schema_validation(deals_data):
    bundles = generate_bundles(deals_data)
    assert len(bundles) > 0

    for b in bundles:
        # Validate through Pydantic schema
        validated = BundleDeal.model_validate(b)
        assert validated.serviceType == "bundle"
        assert validated.secondaryType in ("mobile", "energy", "bank_perk")
        assert validated.regularPrice >= validated.promoPrice
        assert validated.discountMonthly > 0
        assert validated.annualSavings >= 0
        assert validated.totalFirstYear > 0
        assert validated.totalSixMonth > 0


def test_all_fourteen_providers_covered(deals_data):
    bundles = generate_bundles(deals_data)
    providers = {b["provider"] for b in bundles}
    expected = {
        "Aussie Broadband",
        "Superloop",
        "TPG",
        "Vodafone",
        "Mate",
        "SpinTel",
        "Dodo",
        "Tangerine",
        "amaysim",
        "More Telecom",
        "iiNet",
        "Exetel",
        "Optus",
        "Flip",
    }
    assert expected.issubset(providers)


def test_aussie_broadband_bundle_rule(deals_data):
    bundles = [b for b in generate_bundles(deals_data) if b["provider"] == "Aussie Broadband"]
    assert len(bundles) > 0
    for b in bundles:
        assert b["secondaryType"] == "mobile"
        assert b["discountMonthly"] == 5.0
        assert b["annualSavings"] == 60.0
        assert "20GB" in b["secondaryName"]


def test_superloop_bundle_rule(deals_data):
    bundles = [b for b in generate_bundles(deals_data) if b["provider"] == "Superloop"]
    assert len(bundles) > 0
    discounts = {b["discountMonthly"] for b in bundles}
    # 1 SIM: $5/mo, 2 SIMs: $10/mo, 3 SIMs: $15/mo
    assert discounts == {5.0, 10.0, 15.0}
    for b in bundles:
        assert b["secondaryType"] == "mobile"
        assert b["annualSavings"] == round(b["discountMonthly"] * 12, 2)


def test_tpg_bundle_rule(deals_data):
    bundles = [b for b in generate_bundles(deals_data) if b["provider"] == "TPG"]
    assert len(bundles) > 0
    for b in bundles:
        assert b["secondaryType"] == "mobile"
        assert b["discountMonthly"] == 5.0
        assert b["annualSavings"] == 60.0


def test_vodafone_bundle_rule(deals_data):
    bundles = [b for b in generate_bundles(deals_data) if b["provider"] == "Vodafone"]
    assert len(bundles) > 0
    for b in bundles:
        assert b["secondaryType"] == "mobile"
        assert b["discountMonthly"] == 5.0
        assert b["annualSavings"] == 60.0


def test_mate_bundle_rule(deals_data):
    bundles = [b for b in generate_bundles(deals_data) if b["provider"] == "Mate"]
    assert len(bundles) > 0
    for b in bundles:
        assert b["secondaryType"] == "mobile"
        assert b["discountMonthly"] == 10.0
        assert b["annualSavings"] == 120.0


def test_spintel_bundle_rule(deals_data):
    bundles = [b for b in generate_bundles(deals_data) if b["provider"] == "SpinTel"]
    assert len(bundles) > 0
    for b in bundles:
        assert b["secondaryType"] == "mobile"
        assert 3.0 <= b["discountMonthly"] <= 5.0


def test_dodo_bundle_rule(deals_data):
    bundles = [b for b in generate_bundles(deals_data) if b["provider"] == "Dodo"]
    assert len(bundles) > 0
    energy_types = {b["secondaryName"] for b in bundles}
    assert "Dodo Electricity" in energy_types
    assert "Dodo Electricity & Gas" in energy_types

    for b in bundles:
        assert b["secondaryType"] == "energy"
        if b["secondaryName"] == "Dodo Electricity":
            assert b["discountMonthly"] == 5.0
            assert b["annualSavings"] == 60.0
        elif b["secondaryName"] == "Dodo Electricity & Gas":
            assert b["discountMonthly"] == 10.0
            assert b["annualSavings"] == 120.0


def test_tangerine_bundle_rule(deals_data):
    bundles = [b for b in generate_bundles(deals_data) if b["provider"] == "Tangerine"]
    assert len(bundles) > 0
    for b in bundles:
        assert b["secondaryType"] == "bank_perk"
        assert b["promoMonths"] == 12
        # 30% discount
        expected_discount = round(b["regularPrice"] * 0.30, 2)
        assert b["discountMonthly"] == expected_discount
        assert b["promoPrice"] == round(b["regularPrice"] * 0.70, 2)
        assert b["annualSavings"] == round(expected_discount * 12, 2)


def test_amaysim_bundle_rule(deals_data):
    bundles = [b for b in generate_bundles(deals_data) if b["provider"] == "amaysim"]
    assert len(bundles) > 0
    for b in bundles:
        assert b["secondaryType"] == "mobile"
        assert b["discountMonthly"] == 10.0
        assert b["annualSavings"] == 120.0


def test_more_telecom_bundle_rule(deals_data):
    bundles = [b for b in generate_bundles(deals_data) if b["provider"] == "More Telecom"]
    assert len(bundles) > 0
    for b in bundles:
        assert b["secondaryType"] == "bank_perk"
        assert b["discountMonthly"] == 25.0
        assert b["promoMonths"] == 12
        assert b["annualSavings"] == 300.0


def test_iinet_bundle_rule(deals_data):
    bundles = [b for b in generate_bundles(deals_data) if b["provider"] == "iiNet"]
    assert len(bundles) > 0
    for b in bundles:
        assert b["secondaryType"] == "mobile"
        assert b["discountMonthly"] == 5.0
        assert b["annualSavings"] == 60.0


def test_exetel_bundle_rule(deals_data):
    bundles = [b for b in generate_bundles(deals_data) if b["provider"] == "Exetel"]
    assert len(bundles) > 0
    discounts = {b["discountMonthly"] for b in bundles}
    assert discounts == {5.0, 7.50, 10.0}
    for b in bundles:
        assert b["secondaryType"] == "mobile"
        assert b["annualSavings"] == round(b["discountMonthly"] * 12, 2)


def test_optus_bundle_rule(deals_data):
    bundles = [b for b in generate_bundles(deals_data) if b["provider"] == "Optus"]
    assert len(bundles) > 0
    for b in bundles:
        assert b["secondaryType"] == "mobile"
        assert b["discountMonthly"] == 5.0
        assert b["annualSavings"] == 60.0


def test_flip_bundle_rule(deals_data):
    bundles = [b for b in generate_bundles(deals_data) if b["provider"] == "Flip"]
    assert len(bundles) > 0
    for b in bundles:
        assert b["secondaryType"] == "mobile"
        assert b["discountMonthly"] == 5.0
        assert b["annualSavings"] == 60.0


def test_bundle_id_uniqueness(deals_data):
    bundles = generate_bundles(deals_data)
    ids = [b["id"] for b in bundles]
    assert len(ids) == len(set(ids)), f"Duplicate IDs found: {[x for x in ids if ids.count(x) > 1]}"
