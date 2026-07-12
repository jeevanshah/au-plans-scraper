"""Parser regression tests against saved HTML fixtures -- no live network calls."""
from pathlib import Path

from bs4 import BeautifulSoup

from scraper.providers.mobile import amaysim as mobile_amaysim
from scraper.providers.mobile import telstra as mobile_telstra
from scraper.providers.mobile import tpg as mobile_tpg
from scraper.providers.mobile import vodafone as mobile_vodafone
from scraper.providers.mobile import kogan as mobile_kogan
from scraper.providers.mobile import felix as mobile_felix
from scraper.providers.mobile import boost as mobile_boost
from scraper.providers.mobile import aldimobile as mobile_aldi
from scraper.providers.mobile import dodo_mobile
from scraper.providers.mobile import aussie_broadband_mobile as mobile_aussie_broadband
from scraper.providers.nbn import aussie_broadband, dodo, exetel, superloop, tangerine
from scraper.providers.nbn import spintel_nbn as nbn_spintel
from scraper.providers.nbn import telstra as nbn_telstra
from scraper.providers.nbn import iinet as nbn_iinet
from scraper.providers.nbn import vodafone_nbn as nbn_vodafone
from scraper.transform import mobile_plan_to_deal, nbn_plan_to_deal

FIXTURES = Path(__file__).parent / "fixtures"


def _soup(filename: str) -> BeautifulSoup:
    html = (FIXTURES / filename).read_text(encoding="utf-8")
    return BeautifulSoup(html, "lxml")


# ========== NBN tests ==========

def test_aussie_broadband_nbn(monkeypatch):
    monkeypatch.setattr(aussie_broadband, "fetch_static", lambda url: _soup("aussie_broadband_nbn.html"))
    plans = aussie_broadband.scrape()
    assert len(plans) >= 5
    for p in plans:
        assert p.provider == "Aussie Broadband"
        assert p.price_monthly > 0
        assert p.speed_tier.startswith("NBN")


def test_tangerine_nbn(monkeypatch):
    monkeypatch.setattr(tangerine, "fetch_static", lambda url: _soup("tangerine_nbn.html"))
    plans = tangerine.scrape()
    assert len(plans) == 4
    names = {p.plan_name for p in plans}
    assert {"Value", "Value Plus", "Speedy Max", "UltraSpeedy"} <= names
    for p in plans:
        assert p.promo_price is not None
        assert p.promo_price < p.price_monthly


def test_telstra_nbn(monkeypatch):
    monkeypatch.setattr(nbn_telstra, "fetch_static", lambda url: _soup("telstra_nbn.html"))
    plans = nbn_telstra.scrape()
    assert len(plans) == 5
    names = {p.plan_name for p in plans}
    assert names == {"Basic", "Essential", "Premium", "Ultimate", "Ultrafast"}
    for p in plans:
        assert p.price_monthly > 0


def test_dodo_nbn(monkeypatch):
    monkeypatch.setattr(dodo, "fetch_static", lambda url: _soup("dodo_nbn.html"))
    plans = dodo.scrape()
    assert len(plans) == 6  # Fixed Wireless variants excluded
    names = {p.plan_name for p in plans}
    assert names == {"Everyday", "Value", "Fast", "Fast Plus", "Superfast", "Ultrafast"}
    for p in plans:
        assert p.promo_price < p.price_monthly
        assert p.promo_end_date == "2026-09-01"
        assert p.tech_type in ("Fibre", "Fibre and FTTN")


def test_superloop_nbn(monkeypatch):
    monkeypatch.setattr(superloop, "fetch_js", lambda url, **kw: _soup("superloop_nbn.html"))
    plans = superloop.scrape()
    assert len(plans) == 5
    names = {p.plan_name for p in plans}
    assert names == {"Everyday", "Extra Value", "Family Max", "Megaspeed", "Lightspeed"}
    for p in plans:
        assert p.promo_price < p.price_monthly


def test_exetel_nbn(monkeypatch):
    monkeypatch.setattr(exetel, "fetch_static", lambda url: _soup("exetel_nbn.html"))
    plans = exetel.scrape()
    assert len(plans) == 1
    assert plans[0].price_monthly == 80.0
    assert plans[0].promo_price is None
    assert plans[0].speed_tier == "NBN 500/50"


def test_iinet_nbn(monkeypatch):
    monkeypatch.setattr(nbn_iinet, "fetch_js", lambda url, **kw: _soup("iinet_nbn.html"))
    plans = nbn_iinet.scrape()
    assert len(plans) >= 3
    for p in plans:
        assert p.provider == "iiNet"
        assert p.price_monthly > 0
        assert p.speed_tier.startswith("NBN")


# ========== Mobile tests ==========

def test_tpg_mobile(monkeypatch):
    monkeypatch.setattr(mobile_tpg, "fetch_js", lambda url, **kw: _soup("tpg_mobile.html"))
    plans = mobile_tpg.scrape()
    assert len(plans) == 3
    by_name = {p.plan_name: p for p in plans}
    assert by_name["Small Plan"].data_allowance_gb == 25.0
    assert by_name["Medium Plan"].data_allowance_gb == 50.0
    assert by_name["Large Plan"].data_allowance_gb == 100.0
    for p in plans:
        assert p.promo_price < p.price_monthly


def test_telstra_mobile(monkeypatch):
    monkeypatch.setattr(mobile_telstra, "fetch_static", lambda url: _soup("telstra_mobile.html"))
    plans = mobile_telstra.scrape()
    assert len(plans) == 3
    names = {p.plan_name for p in plans}
    assert names == {"Basic", "Essential", "Premium"}
    for p in plans:
        assert p.network == "Telstra"
        assert p.data_allowance_gb > 0


def test_amaysim_mobile(monkeypatch):
    monkeypatch.setattr(mobile_amaysim, "fetch_static", lambda url: _soup("amaysim_mobile.html"))
    plans = mobile_amaysim.scrape()
    assert len(plans) >= 10
    for p in plans:
        assert p.provider == "amaysim"
        assert p.network == "Optus"
        assert p.price_monthly > 0
        assert p.data_allowance_gb is not None and p.data_allowance_gb > 0
        assert not p.is_unlimited_data

    by_name = {p.plan_name: p for p in plans}
    p42 = by_name["42GB"]
    assert p42.promo_price == 12.0
    assert p42.price_monthly == 35.0
    assert p42.promo_price < p42.price_monthly
    assert p42.contract_length == "28-day expiry"

    p10 = by_name["10GB"]
    assert p10.contract_length == "7-day expiry"
    assert p10.promo_price is None


def test_vodafone_mobile(monkeypatch):
    monkeypatch.setattr(mobile_vodafone, "fetch_static", lambda url: _soup("vodafone_mobile.html"))
    plans = mobile_vodafone.scrape()
    assert len(plans) == 3
    for p in plans:
        assert p.provider == "Vodafone"
        assert p.price_monthly > 0
        assert p.data_allowance_gb is not None and p.data_allowance_gb > 0
        assert p.contract_length == "Month-to-month"


def test_kogan_mobile(monkeypatch):
    monkeypatch.setattr(mobile_kogan, "fetch_static", lambda url: _soup("kogan_mobile.html"))
    plans = mobile_kogan.scrape()
    # Fixture: 11 card divs -> 7 distinct tiers.  Duplicates across
    # "Hot deals" + regular "365 days" sections collapse to one via
    # the (GB, price_monthly) dedup key.  (250/350/500GB appear in
    # both sections with identical GB+regular price.)
    assert len(plans) == 7
    for p in plans:
        assert p.provider == "Kogan Mobile"
        assert p.price_monthly > 0
        assert p.data_allowance_gb is not None and p.data_allowance_gb > 0

    by_name = {p.plan_name: p for p in plans}
    # 15GB monthly (flat $20, no promo)
    assert by_name["15GB"].price_monthly == 20.0
    assert by_name["15GB"].promo_price is None
    assert by_name["15GB"].contract_length == "Month-to-month"
    # 80GB monthly (flat $40, no promo)
    assert by_name["80GB"].price_monthly == 40.0
    assert by_name["80GB"].contract_length == "Month-to-month"
    # 60GB monthly (promo: $12 first month, $25 thereafter)
    assert by_name["60GB"].price_monthly == 25.0
    assert by_name["60GB"].promo_price == 12.0
    assert by_name["60GB"].promo_price < by_name["60GB"].price_monthly
    # 140GB 365-day -- no promo (the "$15.00" in card text is
    # "That's only $15.00 per month" annualized marketing blurb)
    assert by_name["140GB"].promo_price is None
    assert by_name["140GB"].price_monthly == 179.9
    # 250GB 365-day -- genuine promo via "Was $190" (member vs non-member)
    assert by_name["250GB"].promo_price == 159.0
    assert by_name["250GB"].price_monthly == 190.0
    assert by_name["250GB"].promo_price < by_name["250GB"].price_monthly
    # 350GB 365-day -- genuine promo via "Was $240"
    assert by_name["350GB"].promo_price == 179.0
    assert by_name["350GB"].price_monthly == 240.0
    assert by_name["350GB"].promo_price < by_name["350GB"].price_monthly
    # 500GB 365-day -- genuine promo via "Non-Member Price: $300"
    assert by_name["500GB"].promo_price == 205.0
    assert by_name["500GB"].price_monthly == 300.0
    assert by_name["500GB"].promo_price < by_name["500GB"].price_monthly


def test_kogan_same_gb_different_contract_kept(monkeypatch):
    """BUG 5 regression: same GB + different contract must produce two distinct plans."""
    from bs4 import BeautifulSoup
    html = """<html><body>
    <div class="tw-rounded-md tw-bg-white tw-shadow">
        <span>140 GB month $30 Unlimited standard calls and texts with data rollover eSIM</span>
    </div>
    <div class="tw-rounded-md tw-bg-white tw-shadow">
        <span>140 GB 365 Day $200 Was $250 Exclusive FIRST Member Offer Unlimited standard calls</span>
    </div>
    </body></html>"""
    soup = BeautifulSoup(html, "lxml")
    monkeypatch.setattr(mobile_kogan, "fetch_static", lambda url: soup)
    plans = mobile_kogan.scrape()
    # Both plans must appear — same GB, different contract_length
    assert len(plans) == 2
    by_contract = {p.contract_length: p for p in plans}
    assert "Month-to-month" in by_contract
    assert "365-day expiry" in by_contract
    assert by_contract["Month-to-month"].price_monthly == 30.0
    assert by_contract["365-day expiry"].price_monthly == 250.0
    assert by_contract["365-day expiry"].promo_price == 200.0


def test_kogan_dedup_identical_gb_contract_removed(monkeypatch):
    """BUG 5 regression: identical (GB, contract) pairs must be deduplicated."""
    from bs4 import BeautifulSoup
    html = """<html><body>
    <div class="tw-rounded-md tw-bg-white tw-shadow">
        <span>80 GB month $40 Unlimited standard calls and texts with data rollover eSIM</span>
    </div>
    <div class="tw-rounded-md tw-bg-white tw-shadow">
        <span>80 GB month $40 Unlimited standard calls and texts with data rollover eSIM</span>
    </div>
    </body></html>"""
    soup = BeautifulSoup(html, "lxml")
    monkeypatch.setattr(mobile_kogan, "fetch_static", lambda url: soup)
    plans = mobile_kogan.scrape()
    assert len(plans) == 1
    assert plans[0].plan_name == "80GB"


def test_kogan_promo_context_does_not_leak_across_siblings(monkeypatch):
    """BUG 6 regression: a card's promo markers must NOT leak into sibling cards
    that share a parent container."""
    from bs4 import BeautifulSoup
    # Two sibling cards under a shared parent — only one has a "Was $X" promo
    html = """<html><body>
    <section>
        <div class="tw-rounded-md tw-bg-white tw-shadow">
            <span>15 GB month $20 Unlimited standard calls and texts with data rollover</span>
        </div>
        <div class="tw-rounded-md tw-bg-white tw-shadow">
            <span>60 GB month $25 Was $60 For the first month $12 thereafter Unlimited standard calls</span>
        </div>
    </section>
    </body></html>"""
    soup = BeautifulSoup(html, "lxml")
    monkeypatch.setattr(mobile_kogan, "fetch_static", lambda url: soup)
    plans = mobile_kogan.scrape()
    assert len(plans) == 2
    by_name = {p.plan_name: p for p in plans}
    # Card 1: 15GB, no promo
    assert by_name["15GB"].price_monthly == 20.0
    assert by_name["15GB"].promo_price is None
    # Card 2: 60GB, genuine promo from "Was $60" / $12 first month
    assert by_name["60GB"].price_monthly == 60.0
    assert by_name["60GB"].promo_price == 12.0
    assert by_name["60GB"].promo_price < by_name["60GB"].price_monthly


def test_felix_mobile(monkeypatch):
    monkeypatch.setattr(mobile_felix, "fetch_static", lambda url: _soup("felix_mobile.html"))
    plans = mobile_felix.scrape()
    assert len(plans) == 3
    names = {p.plan_name for p in plans}
    assert names == {"25GB", "50GB", "Unlimited"}
    for p in plans:
        assert p.provider == "Felix"
        assert p.price_monthly > 0
        assert p.promo_price is not None
        assert p.promo_end_date is None  # "until withdrawn"


def test_boost_mobile(monkeypatch):
    monkeypatch.setattr(mobile_boost, "fetch_static", lambda url: _soup("boost_mobile.html"))
    plans = mobile_boost.scrape()
    # Fixture: 12 distinct plans across short (7/14/28-day) and
    # long-expiry (186/365-day) tiers, deduplicated by (GB, expiry_days)
    assert len(plans) == 12
    for p in plans:
        assert p.provider == "Boost Mobile"
        assert p.price_monthly > 0
        assert p.data_allowance_gb is not None and p.data_allowance_gb > 0
        assert p.network == "Telstra"

    by_key = {(p.data_allowance_gb, p.contract_length): p for p in plans}
    # 365-day long-expiry tiers (previously dropped by the old parser)
    assert (295.0, "365-day expiry") in by_key
    assert (375.0, "365-day expiry") in by_key
    assert by_key[(295.0, "365-day expiry")].price_monthly == 300.0
    assert by_key[(375.0, "365-day expiry")].price_monthly == 330.0
    # 186-day long-expiry
    assert (160.0, "186-day expiry") in by_key
    assert by_key[(160.0, "186-day expiry")].price_monthly == 180.0
    # 28-day short-expiry (same GB value as 186-day tier but different expiry)
    assert (160.0, "28-day expiry") in by_key


def test_boost_dedup_prevents_duplicate_cards(monkeypatch):
    """Regression: duplicate (GB, expiry) cards must produce only one plan."""
    # Two identical productCard divs (same GB, same expiry) — only one plan
    soup = _soup("boost_mobile.html")
    # Find an existing card and clone it
    cards = soup.find_all(class_=lambda c: c and "productCard" in c)
    assert len(cards) > 0
    # Clone the first card and append it, simulating a responsive duplicate
    clone = BeautifulSoup(str(cards[0]), "lxml").find(
        class_=lambda c: c and "productCard" in c
    )
    cards[0].parent.append(clone)

    monkeypatch.setattr(mobile_boost, "fetch_static", lambda url: soup)
    plans = mobile_boost.scrape()
    # The original 12 plans — the duplicated card must NOT add a 13th
    assert len(plans) == 12


def test_aldi_mobile(monkeypatch):
    monkeypatch.setattr(mobile_aldi, "fetch_static", lambda url: _soup("aldi_mobile.html"))
    plans = mobile_aldi.scrape()
    assert len(plans) >= 6
    for p in plans:
        assert p.provider == "ALDImobile"
        assert p.price_monthly > 0
        assert p.data_allowance_gb is not None and p.data_allowance_gb > 0
        assert p.network == "Telstra"
        assert p.contract_length in ("30-day expiry", "365-day expiry")


# ========== Wave 1 provider tests ==========

def test_dodo_mobile(monkeypatch):
    monkeypatch.setattr(dodo_mobile, "fetch_static", lambda url: _soup("dodo_mobile.html"))
    plans = dodo_mobile.scrape()
    assert len(plans) == 3
    by_name = {p.plan_name: p for p in plans}
    assert by_name["25GB"].price_monthly == 25.0
    assert by_name["25GB"].promo_price is None
    assert by_name["40GB"].price_monthly == 30.0
    assert by_name["40GB"].promo_price == 15.0
    assert by_name["40GB"].promo_period_months == 6
    assert by_name["80GB"].price_monthly == 40.0
    assert by_name["80GB"].promo_price == 20.0
    assert by_name["80GB"].promo_period_months == 6
    for p in plans:
        assert p.provider == "Dodo"
        assert p.network == "Optus"
        assert p.contract_length == "Month-to-month"


def test_aussie_broadband_mobile(monkeypatch):
    monkeypatch.setattr(mobile_aussie_broadband, "fetch_static", lambda url: _soup("aussiebb_mobile.html"))
    plans = mobile_aussie_broadband.scrape()
    assert len(plans) == 4
    by_name = {p.plan_name: p for p in plans}
    assert by_name["20GB"].price_monthly == 30.0
    assert by_name["20GB"].promo_price == 15.0
    assert by_name["20GB"].promo_period_months == 3
    assert by_name["45GB"].price_monthly == 40.0
    assert by_name["45GB"].promo_price == 20.0
    assert by_name["100GB"].price_monthly == 50.0
    assert by_name["180GB"].price_monthly == 60.0
    for p in plans:
        assert p.provider == "Aussie Broadband"
        assert p.network == "Optus"
        assert p.contract_length == "Month-to-month"


def test_vodafone_nbn(monkeypatch):
    monkeypatch.setattr(nbn_vodafone, "fetch_static", lambda url: _soup("vodafone_nbn.html"))
    plans = nbn_vodafone.scrape()
    assert len(plans) == 3
    by_name = {p.plan_name: p for p in plans}
    # Plan names read from page text, not derived from Mbps
    assert "Home Fast" in by_name
    assert "Home Superfast" in by_name
    assert "Home Ultrafast" in by_name
    # Speed tiers map correctly
    assert by_name["Home Fast"].speed_tier == "NBN 100/20"
    assert by_name["Home Superfast"].speed_tier == "NBN 500/50"
    assert by_name["Home Ultrafast"].speed_tier == "NBN 1000/50"
    # Prices: promo < regular for all
    assert by_name["Home Ultrafast"].price_monthly == 104.0
    assert by_name["Home Ultrafast"].promo_price == 89.0
    assert by_name["Home Superfast"].price_monthly == 99.0
    assert by_name["Home Superfast"].promo_price == 84.0
    assert by_name["Home Fast"].price_monthly == 99.0
    assert by_name["Home Fast"].promo_price == 84.0
    # Promo months scoped per-tier, not whole-page
    assert by_name["Home Fast"].promo_period_months == 12
    assert by_name["Home Superfast"].promo_period_months == 12
    assert by_name["Home Ultrafast"].promo_period_months == 12
    for p in plans:
        assert p.provider == "Vodafone"
        assert p.promo_price < p.price_monthly
        assert p.contract_length == "Month-to-month"


def test_spintel_nbn(monkeypatch):
    monkeypatch.setattr(nbn_spintel, "fetch_static", lambda url: _soup("spintel_nbn.html"))
    plans = nbn_spintel.scrape()
    assert len(plans) == 4
    by_tier = {p.speed_tier: p for p in plans}
    assert by_tier["NBN 25/10"].price_monthly == 69.95
    assert by_tier["NBN 25/10"].promo_price == 59.0
    assert by_tier["NBN 100/20"].price_monthly == 89.95
    assert by_tier["NBN 100/20"].promo_price == 76.0
    assert by_tier["NBN 500/50"].price_monthly == 89.95
    assert by_tier["NBN 500/50"].promo_price == 79.0
    assert by_tier["NBN 750/50"].price_monthly == 94.95
    assert by_tier["NBN 750/50"].promo_price == 84.0
    for p in plans:
        assert p.provider == "SpinTel"
        assert p.promo_price < p.price_monthly
        assert p.promo_period_months == 6
        assert p.contract_length == "No lock-in contract"


# ========== Transform tests ==========

def test_transform_nbn_deal_shape(monkeypatch):
    monkeypatch.setattr(aussie_broadband, "fetch_static", lambda url: _soup("aussie_broadband_nbn.html"))
    plan = aussie_broadband.scrape()[0]
    deal = nbn_plan_to_deal(plan)
    expected_keys = {
        "id", "provider", "title", "category", "description", "promoPrice",
        "regularPrice", "promoMonths", "validUntil", "url", "serviceType",
        "tier", "techType", "postedAt", "_source",
    }
    assert set(deal.keys()) == expected_keys
    assert deal["serviceType"] == "nbn"
    assert deal["promoPrice"] < deal["regularPrice"]


def test_transform_mobile_deal_shape(monkeypatch):
    monkeypatch.setattr(mobile_telstra, "fetch_static", lambda url: _soup("telstra_mobile.html"))
    plan = mobile_telstra.scrape()[0]
    deal = mobile_plan_to_deal(plan)
    assert deal["serviceType"] == "mobile"
    assert deal["promoPrice"] == deal["regularPrice"]