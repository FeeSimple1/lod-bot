# Card 87 removal audit — October 2026

This report was written before changing the handler, following `agents.md`
section 8. Only the repository's reference documents were consulted.

## Controlling sources

- `Reference Documents/card reference full.txt`, card 87, has one Event
  text: remove one piece in Pennsylvania and remain Eligible. It has no
  Event instruction icon and specifies no piece-type priority.
- `Reference Documents/Manual Ch 8.txt`, §8.3.5, selects a random enemy
  faction, player first, for harmful effects. When friendly pieces must
  be removed, the other friendly faction's pieces are selected first.
- §8.1.2 then supplies the piece priority: enemy Forts/Villages before
  Underground then Active Militia/War Parties, then cubes beginning with
  whichever is fewest (Regulars on a tie). Friendly removal starts with
  cubes beginning with whichever is most (Regulars on a tie, preserving
  the last Tory/Continental when possible), then Active before Underground
  Militia/War Parties, and finally Forts/Villages.

## Mismatch and reproduction

`lod_ai/cards/effects/late_war.py`, `evt_087_lenape`, correctly chooses the
faction to harm but uses a fixed units-before-bases order for every
faction, regardless of whether that faction is friendly or enemy.
Read-only handler reproductions confirmed:

| Executor and pieces in Pennsylvania | Observed removed piece | Required removed piece |
| --- | --- | --- |
| British; one Patriot Fort and one Underground Militia | Militia | Patriot Fort |
| Patriots; one British Fort and one British Regular | Regular | British Fort |
| Patriots; three British Regulars and one Tory | Regular | Tory |

The same fixed order also removes friendly Underground guerrillas before
Active ones and can remove friendly Militia before Continentals.

## Scoped correction and validation

Keep the explicit player piece choice, existing §8.3.5 faction ordering,
single-piece removal to Available, and Remain Eligible effect. Apply the
appropriate §8.1.2 order within the selected faction, using current cube
counts for the British Regular/Tory choice. No shared helper or rule
source changes are needed.

Focused regressions will cover enemy bases, Underground-before-Active
enemy guerrillas, British cube counts and ties, friendly fallback removal
order, human-enemy faction priority, explicit player override, and the
eligibility effect when Pennsylvania is empty.

## Review addendum: protecting the last friendly cube

Review of the first scoped correction found one remaining omission before
its follow-up correction: §8.1.2's instruction to avoid removing the last
friendly Tory/Continental when possible applies when another friendly
piece type is removable, too. With a French executor and one Continental
plus one Militia in Pennsylvania, the fixed cube-first order would still
remove the last Continental. It must remove the Militia instead. Likewise,
a remaining friendly base is an alternative to the last Tory/Continental.

Within the faction selected under §8.3.5, defer a sole Tory/Continental
until every other removable piece type. Keep normal cube-first priority
when two or more are present; remove the last cube when it is the only
piece that can satisfy the Event. Add regressions for these distinctions.
