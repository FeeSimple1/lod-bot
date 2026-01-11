# Card audit (before fixes)

Source: `Reference Documents/card reference full.txt`
Scope: Cards 2, 6, 24, 28, 29, 32

- **Card 2 – Common Sense**: Implementation hardcodes Boston for unshaded and New York City/Philadelphia for shaded instead of selecting any one/two Cities.
- **Card 6 – Benedict Arnold**: Implementation hardcodes Virginia and only removes Underground Militia; should target any one Colony and remove Fort + 2 Militia (Underground then Active) regardless of status.
- **Card 24 – Declaration of Independence**: Unshaded/Shaded effects are inverted vs reference; current code places pieces instead of removing them.
- **Card 28 – Battle of Moore’s Creek Bridge**: Target is locked to North Carolina instead of any one space; function body is mis-indented with `target` defined at module scope.
- **Card 29 – Edward Bancroft, British Spy**: Handler contains stray text and deterministically targets Patriots; needs selectable faction (Patriots or Indians) per reference.
- **Card 32 – Rule Britannia!**: Unshaded locked to Virginia; shaded always gives Resources to Patriots; both should allow any Colony and any faction for Resources.

# Card audit (before fixes)

Source: `Reference Documents/card reference full.txt`
Scope: Cards 23, 24, 54, 77, 83, 105-109

- **Card 23 – Lieutenant Colonel Francis Marion**: Current handler hardcodes South Carolina → Georgia for unshaded and ignores North Carolina/adjacent Provinces and British/Indian choice; shaded removes British pieces only in South Carolina and sends them to Casualties instead of removing from the chosen NC/SC space (Forts last).
- **Card 24 – Declaration of Independence**: Unshaded removal sends Continentals and Fort to Casualties, but the reference only says “remove,” so it should return to Available.
- **Card 54 – Antoine de Sartine, Secretary of the Navy**: Current handler only adjusts a West Indies space blockade count and ignores the shared Squadron/Blockade pool, Unavailable storage, and port blockades required by the reference.
- **Card 77 – General Burgoyne Cracks Down**: Shaded removal sends British pieces to Casualties, but the reference specifies removal (to Available) in three Provinces with Indians, forts last, plus Raid markers.
- **Card 83 – Guy Carleton and Indians Negotiate**: Unshaded should shift Quebec City to Active Support; current handler only shifts one level.
- **Cards 105-109 – Brilliant Stroke!/Treaty of Alliance**: Brilliant Stroke is not implemented as a true interrupt (no pre-action cancel), does not enforce leader involvement, trump chain, or eligibility reset; Treaty of Alliance trump rules and preparations check are incomplete, and BS tracking does not return trumped cards to availability.

# Card audit (before fixes)

Source: `Reference Documents/card reference full.txt`
Scope: Cards 3, 5, 8-9, 11-12, 14, 17, 26-27, 34, 38, 42, 44, 47, 50, 55, 58-61, 63, 69, 71, 74, 76-78, 80, 88-89, 93

- **Card 3 – George Rogers Clark’s Illinois Campaign**: Shaded queues Partisans instead of executing immediately and unshaded removal uses string literals that do not match constants.
- **Card 5 – William Alexander, Lord Stirling**: Unshaded uses `ineligible_next` instead of `ineligible_through_next`; shaded queues free ops without parameters and does not ensure a legal March/Battle.
- **Card 9 – Friedrich Wilhelm von Steuben**: Uses queued free Skirmish ops instead of immediate execution.
- **Card 11 – Thaddeus Kosciuszko, Expert Engineer**: Uses `Patriot_Control` fields in spaces and string-literal piece tags; shaded removal does not prioritize unit removal and does not use shared caps placement.
- **Card 12 – Martha Washington to Valley Forge**: Unshaded ok, shaded ok but needs crash-free handling in broader flow.
- **Card 14 – Overmountain Men Fight for North Carolina**: Uses queued free ops, fixed destination, and executes War Path without Scout/March choices; does not implement British Battle option or free operations.
- **Card 17 – Jane McCrea**: Unshaded uses string matching in space names and string-literal fort tag; shaded uses invalid `to_pool` arg.
- **Card 26 – Josiah Martin**: Unshaded always places Tories instead of Fort/Tory choice and does not use caps; shaded queues free ops without ensuring legal March/Battle.
- **Card 27 – The Queen’s Rangers**: Uses `sp.get("type")` and `sp.get("British_Control")` instead of map/control helpers; Tory sourcing uses move between pools incorrectly and does not prioritize Unavailable.
- **Card 34 – Lord Sandwich’s Secret Correspondence**: Shaded uses `ineligible_next` without guarding against missing set and wrong duration.
- **Card 38 – Sir John Johnson Raises the King’s Royal Greens**: Unshaded hardcodes Quebec, mixes sourcing order, and eligibility handling only clears `ineligible_next`; shaded ignores War Party option.
- **Card 42 – British Attack Danbury**: Uses non-existent "Connecticut" space id.
- **Card 44 – Conway Cabal**: Uses `ineligible_next` instead of `ineligible_through_next` and hardcodes Patriots.
- **Card 47 – German Mercenaries Desert**: Hardcodes Virginia, does not enforce British control for unshaded, and shaded replacement/propaganda logic ignores source selection.
- **Card 50 – French Fleet Arrives**: Unshaded uses `ineligible_next`, shaded hardcodes Virginia and does not place both Patriot/French pieces from any colony.
- **Card 55 – French Fleet Expels British**: Uses queued free ops; shaded/unshaded movement should be mandatory/optional as per text and must avoid West Indies source.
- **Card 58 – Ben Franklin’s Old Aide**: Shaded incorrectly grants Patriot resources; missing Tory-to-Militia replacement in specified spaces.
- **Card 59 – Tronson de Coudray**: Unshaded requires both piece types ≥2 in same space rather than removing any two of each from one space.
- **Card 60 – Joseph Brant, Indian Leader**: Current logic matches but must remain crash-free.
- **Card 61 – Sylvain de Kalb Drills Patriots**: Unshaded uses `ineligible_next` instead of `ineligible_through_next`.
- **Card 63 – British Raid French Fishing Stations**: Logic ok but must remain crash-free.
- **Card 69 – The Battle of Monmouth**: Logic ok but must remain crash-free.
- **Card 71 – French Alliance**: Unshaded computes resources incorrectly and uses `Patriot_Control` and `type` fields instead of control refresh and map metadata.
- **Card 74 – John Stuart, Indian Agent, Escapes Patriots**: Unshaded always grants Indians; shaded removal uses `or` incorrectly and does not total required pieces.
- **Card 76 – Edward Hand Leads Raids on Indians**: Unshaded does not enforce Province selection or specific militia removal ordering; shaded uses invalid `to_pool` arg.
- **Card 77 – Gentlemen Volunteers Join the Patriots**: Shaded uses generic Indian detection, removes to casualties, and adds Raid markers without ensuring Province; unshaded uses direct dict mutation for War Party flipping.
- **Card 78 – Cherry Valley Destroyed by Tories**: Needs constant usage and crash-free checks.
- **Card 80 – Confusion Allows Slaves to Escape**: Hardcodes British, uses prefix hacks and ignores target faction selection.
- **Card 88 – If It Hadn’t Been So Foggy…**: Does not implement Interpretation B movement; removes pieces instead of moving to adjacent spaces and hardcodes Patriots.
- **Card 89 – War Damages Colonies’ Economy**: Replace logic ok but must ensure in-place replacement without invalid locations.
- **Card 93 – Wyoming Massacre**: Uses `sp.get("type")` and ignores adjacency to Reserves; shifts support without neutral check.

# Card audit (before fixes)

Source: `Reference Documents/card reference full.txt`
Scope: Cards 32, 41, 46, 72, 75, 90, 91, 92

- **Card 32 – Rule Britannia!**: Shaded path counts Cities via `sp.get("type") == "City"` instead of using `pick_cities`, and uses a fixed recipient instead of awarding Resources to the executing faction based on Cities under British Control.
- **Card 41 – William Pitt – America Can’t Be Conquered**: Hardcodes Virginia/North Carolina instead of shifting any two Colonies.
- **Card 46 – Edmund Burke on Conciliation**: Unshaded hardcodes Cities instead of placing in any three spaces; shaded shifts specific Cities and uses direct delta without “toward Passive Opposition” behavior.
- **Card 72 – French Settlers Help**: Uses `type`/`reserve` heuristics, ignores shaded no-op requirement, places with caps and wrong piece selection (Fort/Village + War Parties/Militia) and does not respect Available limits or per-faction preferences.
- **Card 75 – Congress’ Speech to the Six Nations**: Reserve provinces derived from `type` field; unshaded does not constrain War Path to one of the Gather spaces; shaded removes from multiple spaces instead of Northwest only, and removal ordering is incomplete.
- **Card 90 – The World Turned Upside Down**: Unshaded only places Forts/Villages with limited location logic and does not allow Village placement for Royalists in Provinces or enforce base-cap legality; does not allow Fort or Village selection in a Province with capacity.
- **Card 91 – Indians Help British Outside Colonies**: Reserve provinces derived from `type` field; unshaded uses caps placement; shaded selection/removal logic does not use the fixed reserve list.
- **Card 92 – Cherokees Supplied by the British**: Does not implement “second Fort or Village in a space where you have one” correctly and does not handle Village/Fort selection rules or base cap checks; shaded no-op must be explicit.
