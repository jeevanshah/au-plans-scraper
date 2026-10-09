from scraper.price_history import build_price_events, collapse_same_day, merge_history


def deal(price, regular=80.0, tier="NBN 50/20", title="Plan", provider="Acme", cycle=None):
    return {"provider": provider, "serviceType": "nbn", "tier": tier, "title": title,
            "promoPrice": price, "regularPrice": regular, "promoMonths": 6, "billingCycleDays": cycle}


def test_records_plausible_change():
    ev = build_price_events([deal(60.0, 85.0)], [deal(60.0, 80.0)], "2026-10-09")
    assert ev and ev[0]["changes"] == {"regularPrice": [80.0, 85.0]}


def test_skips_implausible_jump():
    assert build_price_events([deal(60.0, 400.0)], [deal(60.0, 80.0)], "2026-10-09") == []


def test_skips_ambiguous_duplicates():
    cur = [deal(30.0, tier="160GB"), deal(49.0, tier="160GB")]
    prev = [deal(49.0, tier="160GB"), deal(30.0, tier="160GB")]
    assert build_price_events(cur, prev, "2026-10-09") == []


def test_same_day_flip_flop_dropped():
    a = build_price_events([deal(65.0)], [deal(60.0)], "2026-10-09")
    b = build_price_events([deal(60.0)], [deal(65.0)], "2026-10-09")
    assert collapse_same_day(a + b) == []


def test_merge_prunes_old_events():
    old = [{"date": "2024-01-01", "provider": "Acme", "serviceType": "nbn", "tier": "x",
            "title": "t", "changes": {"promoPrice": [1, 1.5]}}]
    assert merge_history([], old, "2026-10-09") == []
