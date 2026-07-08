# Human-Mode Completeness Audit (ROADMAP Piece 7, part 1)

_Session 72._  Enumerates every card that presents a **player choice**
and diffs it against what the interactive CLI actually collects from a
human seat.  Per the ROADMAP: "any card whose choice silently falls
through to bot selection for a human seat is a bug."

## Method

A card presents a player choice iff its handler reads a
`state.get("card<N>_<key>")` override (the hook a human/CLI is meant to
set).  This audit is generated mechanically from those reads
(`lod_ai/cards/effects/*.py`) and cross-referenced against (a) the bot
setters (`lod_ai/bots/*.py`) and (b) the interactive CLI event path
(`interactive_cli._game_loop`).  The enumeration is pinned by
`tests/test_human_mode_completeness.py` so it cannot silently drift.

## Core finding

**The CLI event path collects none of these choices.**  When a human
plays an Event, the loop shows the card text, lets the human pick the
**shaded/unshaded side**, and then calls `engine.handle_event(...)`
directly — there is no event-choice wizard, and the handlers never
consult an input provider.  So for a human seat, every override key is
absent and the handler resolves the choice with its **non-player
default** (the same code path a bot uses).  Commands and Special
Activities are fully wizarded (`_march_wizard` … `_garrison_wizard`);
**Events are the gap.**

**43 cards** present a player choice and none are human-wired.  Of these:

- **36 are genuinely free player decisions** (space placements, piece
  mixes, sub-option branches) that a human currently cannot make — the
  bot default silently decides.  These are the real Piece 7 bugs.
- **7 are faction-target choices** (18, 44, 48, 66, 67, 80, 88) whose
  default now flows through the §8.3.5 / T7 `target_order` helper
  (S70).  The auto-pick is **rules-faithful**, so a human losing the
  choice is a fidelity gap of lower severity than the free-choice
  cases, though still a choice the human ought to be offered.
- **5 cards** (52, 62, 73, 80, 83) additionally carry bot-specific
  selection logic; the rest fall straight to the shared handler default.

Choice-type breakdown: 26 pure space-selection, 6 with a sub-option
branch, 8 faction-target (7 of them §8.3.5-defaulted), 4 piece-mix.

## The recommended fix (not implemented here — scoped follow-up)

The override keys **already exist and the handlers already honor them** —
only the CLI *collection* layer is missing.  The fix is a per-card
event-choice step in the loop, driven by a registry that maps each card
to its keys and a prompt kind (space picker / faction picker / piece
mix / option).  The table below IS that registry's backbone; the
enforcement test freezes it so new choice-bearing cards must be triaged.
This is sized as its own session(s): 43 prompt specs, each validated
against card text and the handler's expected value shape.

## The registry

| Card | Title | Choice type | Override key(s) | Non-player default |
|-----:|-------|-------------|-----------------|--------------------|
| 4 | The Penobscot Expedition | piece-mix | `base, units` | handler default |
| 5 | William Alexander, Lord Stirling | space | `dest, src` | handler default |
| 7 | John Paul Jones | space | `dest` | handler default |
| 9 | Friedrich Wilhelm von Steuben | space | `spaces` | handler default |
| 11 | Thaddeus Kosciuszko, Expert Engineer | space | `spaces` | handler default |
| 14 | Overmountain Men Fight for North Carolina | space+sub-option | `dest, followup, op, src` | handler default |
| 15 | Morgan’s Rifles | space | `colony` | handler default |
| 16 | Mercy Warren’s “The Motley Assembly” | space | `city, target` | handler default |
| 17 | Jane McCrea Murdered by Indians | space | `space` | handler default |
| 18 | “If it hadn’t been so stormy…” | faction | `target_faction` | §8.3.5 (T7) |
| 19 | Legend of Nathan Hale | space | `targets` | handler default |
| 21 | The Gamecock Thomas Sumter | space | `target` | handler default |
| 23 | Lieutenant Colonel Francis Marion | space | `dst, src, target` | handler default |
| 25 | British Prison Ships | space | `cities` | handler default |
| 26 | Josiah Martin, NC Royal Governor, Plots | space+sub-option | `choice, src` | handler default |
| 27 | The Queen’s Rangers Show for Battle | space | `cities, colonies` | handler default |
| 29 | Edward Bancroft, British Spy | space | `target` | handler default |
| 31 | Thomas Brown and the King’s Rangers | space | `target` | handler default |
| 35 | Tryon Plot | space | `shaded_target, target` | handler default |
| 38 | Johnson’s Royal Greens | piece-mix+space+sub-option | `shaded_choice, unshaded_mix, unshaded_space` | handler default |
| 44 | Earl of Mansfield Recalled From Paris | faction | `target_faction` | §8.3.5 (T7) |
| 47 | Tories Tested | space | `colony` | handler default |
| 48 | God Save the King | faction | `faction` | §8.3.5 (T7) |
| 50 | Admiral d’Estaing, French Fleet Arrives | space | `colony` | handler default |
| 52 | French Fleet Arrives in the Wrong Spot | sub-option | `no_remove_french` | bot-logic |
| 55 | French Navy Dominates Caribbean | sub-option | `do_battle` | handler default |
| 59 | Tronson de Coudray Arrives in America | space | `space` | handler default |
| 62 | Charles Michel de Langlade | space+sub-option | `shaded_choice, target, unshaded_choice` | bot-logic |
| 66 | Don Bernardo Takes Pensacola | faction+piece-mix+space | `mix, shaded_faction, target` | §8.3.5 (T7) |
| 67 | De Grasse Arrives with the French Fleet | faction | `faction` | §8.3.5 (T7) |
| 73 | Sullivan Expedition vs. Iroquois and Tories | space | `space` | bot-logic |
| 74 | Chickasaw Ally with the British | faction+space | `recipient, spaces` | handler default |
| 76 | Edward Hand Raids into Indian Country | space | `space` | handler default |
| 77 | General Burgoyne Cracks Down | space | `space` | handler default |
| 79 | Tuscarora and Oneida Come to Washington | space | `colony` | handler default |
| 80 | Confusion Allows Slaves to Escape | faction+space | `faction, spaces` | §8.3.5 (T7) |
| 81 | Creek and Seminole Active in South | space | `target` | handler default |
| 83 | Guy Carleton and Indians Negotiate | space | `target` | bot-logic |
| 84 | “Merciless Indian Savages” | space | `colonies` | handler default |
| 85 | Indians Help British Raids on Mississippi | piece-mix+sub-option | `mix, shaded_choice` | handler default |
| 87 | Patriots Massacre Lenape Indians | piece-mix | `piece` | handler default |
| 88 | “If it hadn’t been so foggy…” | faction+space | `destinations, target_faction` | §8.3.5 (T7) |
| 93 | Wyoming Massacre | space | `targets` | handler default |

## Part 2 — CLI fuzzing (`tools/human_qa.py`)

`human_qa.py` already drives the real `_game_loop` with a scripted
provider and exercises: meta-commands mid-wizard; budgeted undo at
both Winter-Quarters AND general prompts (with cooldowns, since undo
at literally every prompt would never progress); Brilliant-Stroke
interrupts from a human seat; French pre-Treaty flow; and save/load
every card.  The save/load check is `invariants.check_save_load_roundtrip`,
which ALREADY asserts exact canonical-state + RNG equality across
save->load and dumps a repro on any divergence -- i.e. the ROADMAP's
"round-trip state equality" ask is satisfied.  Verified green across
1775/1776/1778 x all seat combinations (`human_qa --seeds 1-2`).  So
part 2 is effectively ALREADY COVERED by existing infrastructure; the
open Piece 7 work is the part-1 CLI event-choice wiring above.
