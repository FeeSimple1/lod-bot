# Card 55 optional French Battle audit

Written before editing `evt_055_french_navy` in
`lod_ai/cards/effects/middle_war.py`.

The card reference, card 55 unshaded, moves three French Regulars from
the map to West Indies, permits a free French Battle there, and lowers
FNI one level. Manual §5.3 retains ordinary Command requirements unless
the Event overrides them. French Battle requires the Treaty and both
French and Royalist pieces (§3.5.5); French pieces cannot be deployed on
the map or West Indies before Treaty (§2.3.9, §5.1.1). Under §5.1.3,
implement the portions of an Event that can be implemented.

The handler currently defaults `card55_do_battle` to true and calls
`battle.execute` even before the Treaty. A British ineffective-Event
preview of card 55 from an ordinary 1775 setup therefore catches
`ValueError: French cannot Battle before Treaty of Alliance`. Frozen
diagnostics also reproduce this on 1775 seeds 10000, 10010, 10254 and
1776 seed 10027. This is a legal Event with an unavailable optional
Command, not an invalid plan that should be classified as a preview
error. The handler also does not check for French and Royalist presence
before attempting its optional post-Treaty Battle.

The scoped fix will execute the optional French Battle only when the
Treaty is played and both sides have the required pieces in West Indies.
An explicit choice to decline remains authoritative; an explicit request
to Battle cannot override the prerequisites. Legal relocation and FNI
effects still resolve. The shaded British effect is outside this fix.

Regressions will cover the real ineffective-Event preview, pre-Treaty
execution, absent attackers or enemies after Treaty, explicit decline,
and a legal post-Treaty Battle after relocation. No source-of-truth files
or balance baselines will change.

Follow-up inspection before further edits: the shaded side likewise
attempts a Battle even when no opposing pieces remain. A required Battle
still needs both sides' pieces under §3.2.4 and §5.3; §5.1.3 preserves
the relocation when no Battle is possible. Also, the unshaded handler
lowers FNI before its Battle, although the printed card puts that reduction
last. This matters to Battle modifiers. The final fix will check shaded
Battle eligibility and move the FNI reduction after the optional Battle.
Additional tests will cover these prerequisites and effect order.
