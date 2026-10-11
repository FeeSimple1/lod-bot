# Card 48 linked March and Battle audit

Recorded before editing the card handler.

Card 48 unshaded in `Reference Documents/card reference full.txt` grants
British free March to one space and permits free Battle **there**. Manual
§5.3 requires immediate resolution of granted Commands; §8.3.1 applies
the recipient's bot instructions. The one-destination restriction and the
Battle destination are part of the card grant.

`evt_048_god_save_king` in `lod_ai/cards/effects/late_war.py` currently
queues unrelated `march(None)` and `battle(None)` operations. The March
bot planner happens to select one destination, but the Battle planner
then independently selects any eligible space. Reproductions from 1775
seeds 10002, 10052, and 10406 include March to Boston followed by Battle
in New York City. Human March uses an unrestricted wizard and the Battle
wizard permits unrelated spaces without an explicit opportunity to decline.

The fix will queue a serializable linked operation. Resolve a one-space
March, capture its destination, then offer or plan Battle only there.
Human March uses the existing one-destination restriction; Battle uses
the existing Battle wizard with a destination filter and an explicit
yes/no choice. A March with no legal plan cannot create an unrelated
Battle. Both Commands remain free. Tests will exercise bot destination
linkage, no legal Battle at the destination, human one-destination
selection, human acceptance/decline, and saveable queue data.

The shaded handler and source-of-truth files are outside this fix.

Review addendum, before follow-up edits: §3.2.3 allows selecting a March
destination without moving cubes and explicitly activates Militia using
cubes already there. §5.1.3 preserves the possible portions of an Event.
The first implementation's no-movement early return therefore incorrectly
discarded a possible Battle in an already occupied destination. The March
executor also rejected all zero-movement Marches before applying activation.
Correct that British-only executor restriction and allow the linked human
March wizard to select a destination without origins. If the bot has no
movement plan, use §8.4.3 in-place activation priorities (Support first),
then §8.2 ties; if those do not apply, choose an existing Battle space
randomly under §8.3.5. Battle remains tied to the selected destination.

Final review also caught the human paid-Command path: per-destination
payment with a Special Activity checkpoint must include an in-place
destination even when there are no movement entries. The executor now
uses the selected destination order for both payment/checkpoints and
activation. Regression coverage verifies the one-Resource charge exactly
once with and without human checkpoints, and no charge for a free March.
