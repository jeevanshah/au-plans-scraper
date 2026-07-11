You are working in the `au-plans-scraper` repo. Rounds 3-4 fixed real bugs in
Kogan and Boost; verification of round 4 turned up two more latent
fragility issues in kogan.py that aren't causing wrong output today (all 18
tests pass against the current fixture) but would silently break under a
plausible future site change. Fix both defensively now, with tests that
actually exercise the edge case rather than just re-checking today's
fixture still passes.

===========================================================
BUG 5: Kogan dedup keys on GB alone, not (GB, contract_length)
===========================================================

File: scraper/providers/mobile/kogan.py

The dedup set (`seen_gb`, used around line 62/76) tracks only the GB value.
This means if Kogan's real site ever adds two distinct plans that share a
GB size but differ in contract/expiry period (e.g. a 140GB monthly plan
alongside the existing 140GB 365-day plan) -- the same class of bug Boost
had in round 3-4 (BUG 3), which was fixed there by keying dedup on
`(gb, expiry_days)` instead of GB alone -- Kogan would silently drop one of
them as a false duplicate.

Fix: change the dedup key to include whatever field distinguishes plan
family in Kogan's data (contract_length or an equivalent expiry/plan-type
field the parser already extracts per card), following the same pattern
used in boost.py's fix. Don't dedupe on GB alone.

Test: like Boost's `test_boost_dedup_prevents_duplicate_cards`, add a
synthetic test that constructs two cards with the same GB but different
contract_length/expiry (not just a byte-identical clone), and assert both
plans are returned distinctly. Also keep/add a true-duplicate case
(identical GB AND contract_length) and assert that one IS still deduped --
so the test proves both halves of the fix (real duplicates removed,
same-GB-different-plan kept).

===========================================================
BUG 6: Kogan's promo-price context leaks from parent element
===========================================================

File: scraper/providers/mobile/kogan.py

`ctx = parent.get_text() + txt` (around line 81) pulls in the full text of
the card's *parent* element, not just the card itself, before scanning for
promo-price markers ("Was $X", "Non-Member Price: $X", etc). In the current
fixture each card's immediate parent happens to wrap exactly one card, so
this doesn't leak anything today -- but if Kogan's real site ever groups
multiple sibling cards under a shared parent container (as several other
providers in this project do, e.g. Vodafone/amaysim group cards under
section wrappers), this would let one card's promo/price text bleed into
another card's parsed output.

Fix: scope `ctx` to the card element itself (or the smallest ancestor that
still reliably contains the promo marker for a single card, if the promo
text genuinely lives outside the immediate card div in Kogan's real markup
-- check the actual fixture structure to confirm exactly how far up you
need to go, don't just remove the parent lookup blindly if the real promo
markers depend on it).

Test: construct a synthetic case with two sibling cards sharing a parent
container, where only one has a "Was $X" marker, and assert the OTHER card
does NOT pick up that promo value. This proves the leak is closed, not just
that today's fixture still parses correctly.

===========================================================
CONSTRAINTS
===========================================================

- Don't touch any other provider or the already-passing tests for them
- Both fixes should be defensive/structural (fix the actual scoping logic),
  not special-cased to make today's fixture happen to still pass
- Run `pytest tests/ -v` and confirm all tests pass, including the new
  synthetic edge-case tests for both bugs
- After this round, we're done with the bug-hunt loop on the mobile
  scrapers -- report a final summary of all providers added across rounds
  1-5 and confirm nothing else looks fragile in kogan.py/boost.py from a
  final read-through, but don't go looking for new provider bugs beyond
  these two specific fixes
