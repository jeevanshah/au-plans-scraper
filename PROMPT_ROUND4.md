You are working in the `au-plans-scraper` repo. Round 3 fixed two real
parsing bugs in Kogan and Boost, but verification found two more latent bugs
introduced/exposed by those very fixes. Neither is caught by the current
tests, so fix the root cause AND add an assertion that would have caught it.

===========================================================
BUG 3: Boost Mobile's dedup does nothing (dead code)
===========================================================

File: scraper/providers/mobile/boost.py

`seen: set[tuple[float,int]] = set()` is declared and `seen.add((gb,
expiry_days))` is called, but there is no `if (gb, expiry_days) in seen:
continue` (or equivalent) check anywhere in the file. The dedup set is
populated but never read. It currently produces the correct 12-plan count
only because tests/fixtures/boost_mobile.html happens to have no literal
duplicate cards for the same (GB, expiry) pair -- but Boost's real live page
may repeat card markup across responsive breakpoints the way Vodafone and
Kogan's pages do, in which case this scraper will silently double-count
plans in production.

Fix: add the missing skip check so `seen` actually prevents duplicate
(gb, expiry_days) pairs from producing multiple MobilePlan entries.

Test: add a small synthetic-duplication test (or extend the existing
fixture-based test) that proves a repeated card for the same (GB, expiry)
pair is only counted once -- e.g. duplicate one plan card in a copy of the
fixture (or construct a minimal HTML snippet with two identical cards
in-test) and assert scrape() still returns only one plan for that pair.
Don't just trust that the real fixture has no duplicates today.

===========================================================
BUG 4: Kogan's widened "$" regex now captures marketing-blurb prices as promo_price
===========================================================

File: scraper/providers/mobile/kogan.py

The round-3 fix widened DOLLAR_RE to `\$\s*(\d+\.?\d*)` to handle "$ 20"
style spacing -- correct for the monthly tiers, but it also now matches
unrelated dollar figures in marketing copy on the 365-day plan cards, e.g.
"That's only $15.00 per month" (an annualized cost-average blurb, not a
promo price). This is currently misassigned as promo_price on the
140GB/250GB/350GB 365-day tiers (140GB shows promo_price=$15.00,
250GB=$13.25, 350GB=$14.92) even though none of these plans have a real
promo -- verify against the actual fixture text/site copy whether ANY of
the 365-day tiers have a genuine promo price at all, and if not, these
fields should be None.

Fix: scope promo-price extraction more precisely -- e.g. only look for a
promo price within a specific labeled substring (however the real promo
price is actually marked up on cards that DO have one, like the 60GB and
500GB tiers which have real promos per round 3's own findings), rather than
grabbing any "$X per month" text found anywhere in the card. The "per
month"-average blurb text is a distinguishing pattern you can explicitly
exclude, or better: anchor the promo-price regex to whatever structural
marker (CSS class, "was $X"/"first month" label, etc.) actually indicates a
genuine promo on this page, the same way the 60GB card's real promo is
identified.

Test: extend test_kogan_mobile to assert promo_price is None for the
140GB/250GB/350GB 365-day tiers (the ones with no real promo), not just
checking the tiers that already have correct values. This is the assertion
that would have caught this bug.

===========================================================
GENERAL INSTRUCTION
===========================================================

Both of these bugs exist because a fix for one case (missing plans, wrong
spacing) had a side effect on an adjacent case (a dedup path, an unrelated
price mention) that wasn't checked. Before finishing, re-read through
kogan.py and boost.py once more end-to-end and sanity-check every field on
every returned plan against the actual fixture content by hand -- not just
the fields the previous round's bug touched -- to catch anything else in
the same vein. Run `pytest tests/ -v` and confirm all tests pass, including
the two new assertions above.
