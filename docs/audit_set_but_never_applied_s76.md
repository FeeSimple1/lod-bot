# "Set But Never Applied" Audit — S76

Source: fs-bot (Falling Sky sibling project) card-effect bug-class brief.
The class: an event handler *records* an effect (flag, grant, restriction,
modifier) that the engine then never *reads* — or reads on only one of two
parallel code paths.  Procedure per the brief: set-vs-read diff first, then
each sub-pattern with card text in hand.

## Verdicts

### 1. Flags set but never read — ONE REAL BUG, FIXED

Set-vs-read diff over `state[...]` writes in `cards/effects/` found one
orphan: **card 22 (The Newburgh Conspiracy) shaded** — "Immediately execute
Tory Desertion as per Winter Quarters Round" — set
`state["winter_flag"] = "TORY_DESERTION_IMMEDIATE"`, and *nothing* reads
`winter_flag`.  History: §6.6 Desertion was made unconditional at every WQ
(test_year_end.py: "runs every WQ without winter_flag"), which orphaned the
flag; the shaded side degenerated to a history line and no board effect.
Cards 12/13 got the immediate-call pattern for Patriot Desertion in an
earlier session; card 22 was the missed Tory-side twin.

Fix: `evt_022` shaded now calls `year_end._tory_desertion(state)` directly
(same pattern as cards 12/13); dead `winter_flag` reference removed from the
year_end module docstring.  Tests: 10 Tories → 2 desert immediately;
4 Tories → true no-op (`4 // 5 == 0`); no flag left in state.

Canary: 1775 seed 3 flipped BRITISH→INDIANS (Tory Desertion now actually
fires) — explained, rebaselined.

### 2. Timed eligibility vs end-of-card reset — ONE REAL BUG, FIXED

Both directions checked at the OBSERVATION POINT (after `_prepare_card`'s
adjustment), per the brief, not at the set-site:

* "Ineligible through next card" surviving the did-not-act→Eligible reset:
  **conforming**.  Manual §2.3.9 play note ("will be Ineligible FOR THE NEXT
  card") confirms the current card's queue is unaffected by design — the
  initial suspicion that the current card should also be affected was wrong.
* "Remain Eligible" one-shot consumption: **bug found**.  A grant to a
  faction that did NOT act that card (card 67 can name the non-executing
  partner) sat stale in `state["remain_eligible"]` and wrongly retained that
  faction after some LATER card's Command.  Fix: `engine._prepare_card` pops
  leftovers after the adjustment — the grant's window is its own card only.
* Collision (both flags on one faction): penalty beats retention —
  **conforming**, now gated.

Tests: `lod_ai/tests/test_eligibility_observation_point.py` (4 gates).

### 3. Quantity/region restrictions on granted free actions — CONFORMING

Every `_plan_bot_free_op` branch honors the queued `loc` pin:
battle/battle_plus2 filter candidates to `loc`; march passes it to
`plan_free_march`; muster/gather validate the pin and return None (genuine
decline) when illegal; rally and the free-SA planners validate via
`_option_for(loc)`/`_legal(loc)`.  Pinned-illegal → decline already gated
(test_bot_free_ops: pinned French Muster in a non-Rebellion space is None).
Human seats with a pinned loc dispatch at that loc.  FIFO order preserved
(card 66's "march to Florida, then battle there" resolves in sequence).

### 4. Wrong beneficiary — PREVIOUSLY COVERED

T7 `beneficiary_order` (§8.3.5) plus the S73/S75 executor-vs-hardwired
sweeps (e.g. card 52's battler was hardwired FRENCH, fixed Session 47;
card 66 first_beneficiary).  No new instances in this pass.

### 5. Modifier reaching all calculators (dual-calculator drift) — CONFORMING

`battle_plus2` grants (cards 52 "anywhere", 66 "Florida"): the resolver
receives the +2 (`dispatcher` registers `choices={"force_bonus": 2}` →
`battle.py` `attacker_bonus` → `att_force`).  The planning side selects the
space by §8.4.1 "affect the most enemy pieces" and performs NO force-level
calculation, so there is no second calculator the bonus could fail to reach.
`bot_battle_scores` (B12/P4 Command selection, card 51 march-to-battle) is
never used to gate a +2 grant.  If a future card gates a bonus battle on
winnability, thread the bonus into `bot_battle_scores` then.

## Residual (noted, not fixed)

`year_end._tory_desertion` / `_patriot_desertion` no-bots fallback removes
the remainder in dict order.  In engine games `bots` is always passed, so
the fallback only fires for direct card-handler calls (cards 12/13/22) and
human-British WQ without CLI choice — a Part-B-style dict-order candidate
for a future pass, shared with the pre-existing cards 12/13 usage.

## Battery

1500 pytest green (canary rebaselined as above), playbook goldens green,
clean_sweep_gate seeds 1-20 clean, fresh 120-game invariant soak clean.
