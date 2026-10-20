# Card 1: human choice audit

Pre-edit audit, 2026-10-20. Source: `Reference Documents/card reference full.txt`,
card 1, lines 7–11.

The unshaded text specifies “In one space with British” and the shaded text
specifies “Patriots free March to and free Battle in one space.” Both sides
then place two Propaganda in the same space; the shaded political shift occurs
after the free Commands.

The handler in `lod_ai/cards/effects/late_war.py::evt_001_waxhaws` always selects
the space with non-player priorities. It has no `card1_*` input override and
`lod_ai/event_choices.py::EVENT_CHOICES` has no entry for card 1. Consequently a
human cannot choose an alternate legal target, even when several targets exist.
The existing hook inventory does not detect this omission because it only
discovers choices that handlers already expose.

The shaded handler correctly queues March, Battle, then its printed aftermath.
However `Engine._drain_free_ops` uses human planning wizards only when a queued
operation has no preset location. Card 1 supplies a preset destination, so
human Patriots cannot choose March origins or piece counts, or Battle
activation. The raw dispatch cannot supply those decisions.

Required corrections: expose a validated target override and human target
menu; run location-restricted human March/Battle wizards for the shaded free
Commands; retain the current non-player target and operation planners. The
March destination and Battle space must remain the selected Event space, and
the printed Propaganda/Neutral shift must remain after those Commands.

This audit identifies no need to change the printed effects, bot priorities,
or the existing card 48 linked-command behavior.
