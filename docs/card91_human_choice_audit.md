# Card 91: human choice audit

Pre-edit audit, 2026-10-20. Source: `Reference Documents/card reference full.txt`,
card 91, lines 1164–1168.

The unshaded text says “Place one Village and two War Parties in one Indian
Reserve Province.” The shaded text says “Remove one Village in one Indian
Reserve Province.” Thus the executing player selects one Reserve Province;
the shaded selection must contain a Village to remove.

`lod_ai/cards/effects/early_war.py::evt_091_indians_help` always selects the
unshaded space by non-player base-room/War-Party priorities, and always selects
the shaded space by the Random Spaces table. It exposes no `card91_*` override.
`lod_ai/event_choices.py::EVENT_CHOICES` consequently has no card 91 menu.
A live LLM in the Indian human seat selected the unshaded Event and observed
an automatic Florida placement without a Reserve choice.

Required correction: expose a validated `card91_target` and human Reserve menu
for each side, preserving those exact existing non-player defaults when no
valid player choice is supplied. Preserve piece availability, base caps, and
Underground placement. Add regression tests for alternate legal choices on
both sides and invalid targets.
