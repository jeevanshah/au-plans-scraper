"""Parser regression tests against saved HTML fixtures -- no live network calls."""
from pathlib import Path

from bs4 import BeautifulSoup

from scraper.providers.mobile import telstra as mobile_telstra
from scraper.providers.mobile import tpg as mobile_tpg
from scraper.providers.nbn import aussie_broadband, dodo, exetel, superloop, tangerine
from scraper.providers.nbn import telstra as nbn_telstra
from scraper.transform import mobile_plan_to_deal, nbn_plan_to_deal

FIXTURES = Path(__file__).parent / "fixtures"


def _soup(filename: str) -> BeautifulSoup:
    html = (FIXTURES / filename).read_text(encoding="utf-8")
    return BeautifulSoup(html, "lxml")


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
    assert deal["promoPrice"] == deal["regularPrice"]  # Telstra mobile has no promo in this fixture
