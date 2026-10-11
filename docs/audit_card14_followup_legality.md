# Card 14 follow-up legality audit

Written before changing `evt_014_overmountain_men` in
`lod_ai/cards/effects/middle_war.py`.

Card 14 in `Reference Documents/card reference full.txt` grants Indians
a free Scout or March to North Carolina or Southwest, followed by Indian
War Path or British free Battle there. Its shaded side grants Patriot
free March to and free Battle in either named space. Manual §5.3 retains
ordinary prerequisites; §5.1.3 requires implementing the portions possible.

The strict diagnostic batch reproduces a card 14 preview error in 1775
seed 10284 and 1776 seed 10200: a lone Patriot Fort qualifies for the
handler's broad enemy-presence test, but the handler always requests
War Path option 1. Under §4.4.2, option 1 removes a Rebellion unit;
Fort removal instead requires option 3, no Rebellion units, and two
Underground War Parties. The existing fixed-space free War Path planner
already implements these option requirements and §8.7.1's maximum-removal
priority. It should supply the option, or decline when none is legal.

The handler also discards all follow-up effects when the first movement
cannot occur, even if a legal War Path or Battle is already possible at
the destination. Conversely, its Battle calls do not check for the two
factions' required pieces (§3.2.4, §3.3.3). It accepts any on-map explicit
destination, although the Event names only North Carolina and Southwest.

Scoped fixes: restrict destinations to the printed choices, keep each
implementable effect, select a legal War Path option, and invoke Battles
only with the requisite opposing pieces. Tests cover Fort-only targets,
one/two Underground War Parties, maximum unit removal, unavailable first
movement, and unavailable follow-up attacks. Movement planning and other
card handlers are outside this audit.
