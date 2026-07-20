# Piece 3 audit — Session 75 (event_eval flags + dict-order scan classification)

## Part A — P2/F2/I2 Event-or-Command bullet audit  [FIXES LANDED S75]

Method: printed bullet lists (Manual §8.5/§8.6/§8.7 + the flowchart
reference txts) diffed against the three `_faction_event_conditions`
implementations, PLUS an empirical differ (run every flagged card's
handler on a rich state; observe piece/resource deltas; diff vs the
CARD_EFFECTS flags).

FIXED (S75):
* **Card 13 shaded mis-flag** — handler places ACTIVE Militia only
  (empirical dMILITIA_A=4, dMILITIA_U=0); `places_patriot_militia_u`
  was True.  P2-2 no longer fires on it.
* **P2-2 "has none already" scoping** — the Manual's "none" scopes to
  the UNDERGROUND Militia being placed (grammatical antecedent); the
  code excluded spaces with ANY militia.  A space holding only Active
  Militia now qualifies.
* **P2-2 target-awareness** (the S63 "card-42 class" fix applied to
  the Patriot list): the bullet now tests only spaces where THIS
  card's Militia can land — new `militia_in` domains (None/tuple/
  "CITIES"/"COLONIES"/"TORY_OR_INDIAN"/"MA_OR_INDIAN") and
  `militia_via_tory` (replacement cards need a Tory in-space) on all
  17 flagged cards.  Live example: card 62's Militia can only reach
  Northwest — an Active-Support space elsewhere no longer fires P2.
* **F4 "(including a free French Battle)" (Manual §8.6)** — cards 52
  (executor free Battle+2) and 66 shaded (French-or-Patriots free
  March+Battle) now carry `inflicts_british_casualties`.

CONFORMING (verified, no change): all French F1-F3/F5-F6, Indian
I1-I4, Patriot P1/P3-P5.  The FNI/Blockade sub-paths on the three
bullet-1s are Manual-parenthetical-cited (§8.5 line 467, §8.6/§8.7
equivalents) even though the flowchart cards abbreviate them.

NOTED, not changed: P5's 25-piece count omits Washington (whether a
Leader is a "piece on the map" for this count is a Glossary read —
candidate Q24 if it ever matters); F3 reads "French pieces" as
Regulars only (ignores Squadrons/Leader — same class).

## Part B — dict-order first-fit scan classification  [EXECUTED S76]

All conversions below LANDED (S76).  Two sites needed MORE than the
classified §8.2 treatment — their toward-Neutral shifts are
side-sensitive, caught live by the §8.3.3 net-shift invariant during
the batch battery: card 93 (routed through §8.3.6
select_support_shift_spaces, target=0) and card 1 (side-aware keys:
shaded = card-51/T8 winnable-Battle target + non-royalist-favoring
shift; unshaded = Continentals-removed then pop-weighted gain).
The borderline pool-removal analogues remain out of scope as
documented.

Verdicts from the S75 sweep (each verified against the printed card
text).  §8.2 treatment = route through pick_by_priority /
pick_random_spaces preserving any substantive key.

EQUAL-CANDIDATES (fix = §8.2):
* LW card 1 (both): "one space with British" — `eligible[0]`.
* MW card 8 unshaded: Activate 3 Militia anywhere — first-3 dict scan.
* MW card 11 shaded: 2-of-N Rebellion spaces — first-2.
* MW card 17 unshaded: one Reserve with a Patriot Fort — first-fit.
* MW card 47 both sides: the one Colony — first-fit.
* MW card 50 shaded: "any one Colony" — first-fit.
* MW card 59 unshaded: both-types-first filter is real §8.1.1, but the
  tie among both-holding spaces is dict order.
* MW card 74 shaded: 2-of-N removal spaces — first-2.
* MW card 76 unshaded: the one Province with 3+ Militia — first-fit.
* MW card 77 shaded: 3 shared Provinces — first-3; unshaded: the one
  Village space — first-fit.
* MW card 78 shaded: 4 Tory/Indian spaces get Militia — first-4.
* LW card 39 unshaded: 3 Cities toward Neutral — dict order, should be
  §8.3.6 select_support_shift_spaces + §8.2.
* LW card 48 shaded: the 3 source spaces AND each destination (first
  adjacent) — both dict-order.
* EW card 92 unshaded: second Fort/Village space — first sorted().

CAPPED-SWEEP ("up to N" = §8.2 selection): MW card 9 (3 skirmish
spaces), EW card 13 helper `_pick_spaces_with_militia` (sorted[:4]),
MW card 93 (first-3 of qualifying colonies — note the S73 CLI layer
already collects this for humans).

SHEET-PRIORITY (keep; cite): LW card 70 per-executor removal tiers
(bot sheet Q2) — but intra-tier ties are dict order (§8.2 residual).

BORDERLINE (pool-removal analogues, low priority): EW 20/33/68,
MW 55 both sides / 78 unshaded, LW 57 shaded.  Free-op destination:
MW card 5 `_pick_move` first-fit — should use the March/Battle
priority (`battle.bot_march_battle_target`, the card-51/T8 pattern).
Also `winter_quarters._lose_fort_or_village` uses raw `rng.choice`
instead of `pick_random_spaces` (§8.2).

Next session: execute Part B fixes (mechanical; battery + canary +
large-N after).
