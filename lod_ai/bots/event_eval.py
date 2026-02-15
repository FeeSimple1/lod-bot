# lod_ai/bots/event_eval.py
# ---------------------------------------------------------------
# Static lookup table for bot event-condition evaluation.
#
# Replaces keyword matching against card text.  Each entry records
# what the unshaded and shaded sides CAN do, in terms the four bot
# flowcharts care about.
#
# Fields reflect what a card CAN do, not what it always does.
# If a shaded side is "(none)" / null, all fields are False.
# ---------------------------------------------------------------

_F = dict(
    shifts_support_royalist=False,
    shifts_support_rebel=False,
    places_british_pieces=False,
    places_patriot_militia_u=False,
    places_patriot_fort=False,
    places_french_from_unavailable=False,
    places_french_on_map=False,
    places_village=False,
    removes_patriot_fort=False,
    removes_village=False,
    adds_british_resources_3plus=False,
    adds_patriot_resources_3plus=False,
    adds_french_resources=False,
    inflicts_british_casualties=False,
    grants_free_gather=False,
    is_effective=False,
)


def _e(**kw):
    """Return a flags dict with *kw* overrides set to True."""
    d = dict(_F)
    for k, v in kw.items():
        d[k] = v
    return d


# All False — used for shaded=(none) / null cards and truly blank sides.
_NONE = dict(_F)

CARD_EFFECTS = {
    # ------------------------------------------------------------------
    # Card 1: Waxhaws Massacre
    # U: remove 2 Continentals to Casualties, shift toward Active Support,
    #    place 2 Propaganda
    # S: Patriots free March + Battle, Propaganda, shift toward Neutral
    # ------------------------------------------------------------------
    1: {
        "unshaded": _e(
            shifts_support_royalist=True,
            inflicts_british_casualties=False,  # inflicts REBEL casualties
            is_effective=True,
        ),
        "shaded": _e(
            shifts_support_rebel=False,  # toward Neutral, not rebel
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 2: Common Sense
    # U: place 2 Regulars + 2 Tories in City, Propaganda, Brit Res +4
    # S: shift 2 Cities toward Active Opposition, Propaganda
    # ------------------------------------------------------------------
    2: {
        "unshaded": _e(
            places_british_pieces=True,
            adds_british_resources_3plus=True,
            is_effective=True,
        ),
        "shaded": _e(
            shifts_support_rebel=True,
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 3: George Rogers Clark's Illinois Campaign
    # U: Remove all Patriot pieces in NW and SW
    # S: place 2 Militia + free Partisans in NW and SW
    # ------------------------------------------------------------------
    3: {
        "unshaded": _e(
            removes_patriot_fort=True,  # removes ALL Patriot pieces (incl Forts)
            is_effective=True,
        ),
        "shaded": _e(
            places_patriot_militia_u=True,
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 4: The Penobscot Expedition
    # U: Remove 3 Militia, Patriot Res -2
    # S: Place 1 Fort/Village + 3 Militia/WP in Massachusetts
    # ------------------------------------------------------------------
    4: {
        "unshaded": _e(
            is_effective=True,
        ),
        "shaded": _e(
            places_patriot_militia_u=True,
            places_patriot_fort=True,
            places_village=True,
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 5: William Alexander, Lord Stirling
    # U: Patriots Ineligible through next card
    # S: Patriots free March + Battle
    # ------------------------------------------------------------------
    5: {
        "unshaded": _e(
            is_effective=True,
        ),
        "shaded": _e(
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 6: Benedict Arnold
    # U: Remove 1 Patriot Fort to Casualties + 2 Militia from Colony
    # S: Remove 1 British Fort + 2 British cubes to Casualties
    # ------------------------------------------------------------------
    6: {
        "unshaded": _e(
            removes_patriot_fort=True,
            is_effective=True,
        ),
        "shaded": _e(
            inflicts_british_casualties=True,
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 7: John Paul Jones
    # U: Brit Res +3, lower FNI, place up to 2 Brit Regs
    # S: Patriot Res +5, raise FNI
    # ------------------------------------------------------------------
    7: {
        "unshaded": _e(
            places_british_pieces=True,
            adds_british_resources_3plus=True,
            is_effective=True,
        ),
        "shaded": _e(
            adds_patriot_resources_3plus=True,
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 8: Culpeper Spy Ring
    # U: Activate 3 Patriot Militia
    # S: Remove 3 British cubes to Casualties
    # ------------------------------------------------------------------
    8: {
        "unshaded": _e(
            is_effective=True,
        ),
        "shaded": _e(
            inflicts_british_casualties=True,
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 9: Friedrich Wilhelm von Steuben
    # U: British Skirmish in up to 3 spaces
    # S: Patriots Skirmish in up to 3 spaces
    # ------------------------------------------------------------------
    9: {
        "unshaded": _e(
            is_effective=True,
        ),
        "shaded": _e(
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 10: Benjamin Franklin Travels to France
    # U: Shift 2 Cities toward Active Support
    # S: French Res +3, Patriot Res +2
    # ------------------------------------------------------------------
    10: {
        "unshaded": _e(
            shifts_support_royalist=True,
            is_effective=True,
        ),
        "shaded": _e(
            adds_french_resources=True,
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 11: Thaddeus Kosciuszko
    # U: Remove 2 Patriot Forts
    # S: In 2 Patriot-controlled spaces, remove piece + add Fort
    # ------------------------------------------------------------------
    11: {
        "unshaded": _e(
            removes_patriot_fort=True,
            is_effective=True,
        ),
        "shaded": _e(
            places_patriot_fort=True,
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 12: Martha Washington to Valley Forge
    # U: Execute Patriot Desertion
    # S: Patriot Res +5
    # ------------------------------------------------------------------
    12: {
        "unshaded": _e(
            is_effective=True,
        ),
        "shaded": _e(
            adds_patriot_resources_3plus=True,
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 13: "...the origin of all our misfortunes"
    # U: Execute Patriot Desertion
    # S: In up to 4 spaces add Active Militia
    # ------------------------------------------------------------------
    13: {
        "unshaded": _e(
            is_effective=True,
        ),
        "shaded": _e(
            places_patriot_militia_u=True,  # places Active Militia (still patriot militia)
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 14: Overmountain Men Fight for North Carolina
    # U: Indians free Scout/March + War Path/Battle in NC or SW
    # S: Patriots free March + Battle in NC or SW
    # ------------------------------------------------------------------
    14: {
        "unshaded": _e(
            is_effective=True,
        ),
        "shaded": _e(
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 15: Morgan's Rifles
    # U: Shift Virginia toward Active Support, place 2 Tories
    # S: Patriots free March + Battle + Partisans
    # ------------------------------------------------------------------
    15: {
        "unshaded": _e(
            shifts_support_royalist=True,
            places_british_pieces=True,
            is_effective=True,
        ),
        "shaded": _e(
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 16: Mercy Warren's "The Motley Assembly"
    # U: Place 2 Tories anywhere
    # S: Shift 1 City to Passive Opposition
    # ------------------------------------------------------------------
    16: {
        "unshaded": _e(
            places_british_pieces=True,
            is_effective=True,
        ),
        "shaded": _e(
            shifts_support_rebel=True,
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 17: Jane McCrea Murdered by Indians
    # U: Remove 1 Patriot Fort from Indian Reserve Province
    # S: Remove 1 Indian Village
    # ------------------------------------------------------------------
    17: {
        "unshaded": _e(
            removes_patriot_fort=True,
            is_effective=True,
        ),
        "shaded": _e(
            removes_village=True,
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 18: "If it hadn't been so stormy..."
    # U: Any 1 Faction Ineligible through next card
    # S: (none)
    # ------------------------------------------------------------------
    18: {
        "unshaded": _e(
            is_effective=True,
        ),
        "shaded": dict(_NONE),
    },
    # ------------------------------------------------------------------
    # Card 19: Legend of Nathan Hale
    # U: Patriot Res -4
    # S: Place 3 Militia, Patriot Res +3
    # ------------------------------------------------------------------
    19: {
        "unshaded": _e(
            is_effective=True,
        ),
        "shaded": _e(
            places_patriot_militia_u=True,
            adds_patriot_resources_3plus=True,
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 20: Continental Marines
    # U: Remove 4 Continentals from map to Available
    # S: Place 4 Continentals in New Jersey
    # ------------------------------------------------------------------
    20: {
        "unshaded": _e(
            is_effective=True,
        ),
        "shaded": _e(
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 21: The Gamecock Thomas Sumter
    # U: Shift SC or GA toward Active Support
    # S: Patriots free March + Battle in SC or GA
    # ------------------------------------------------------------------
    21: {
        "unshaded": _e(
            shifts_support_royalist=True,
            is_effective=True,
        ),
        "shaded": _e(
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 22: The Newburgh Conspiracy
    # U: Remove 4 Patriot Militia/Continentals in Colony
    # S: Immediately execute Tory Desertion
    # ------------------------------------------------------------------
    22: {
        "unshaded": _e(
            is_effective=True,
        ),
        "shaded": _e(
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 23: Lt Col Francis Marion
    # U: Move all Patriot units from NC/SC to adjacent
    # S: Remove 4 British units from NC/SC if Militia there
    # ------------------------------------------------------------------
    23: {
        "unshaded": _e(
            is_effective=True,
        ),
        "shaded": _e(
            inflicts_british_casualties=False,  # removes to Available, not Casualties
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 24: Declaration of Independence
    # U: Remove 2 Cont, 2 Militia, 1 Patriot Fort
    # S: Place up to 3 Militia + Propaganda, 1 Fort
    # ------------------------------------------------------------------
    24: {
        "unshaded": _e(
            removes_patriot_fort=True,
            is_effective=True,
        ),
        "shaded": _e(
            places_patriot_militia_u=True,
            places_patriot_fort=True,
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 25: British Prison Ships
    # U: Shift 2 Cities toward Passive Support
    # S: In 2 Cities place Militia + shift toward Passive Opposition + Propaganda
    # ------------------------------------------------------------------
    25: {
        "unshaded": _e(
            shifts_support_royalist=True,
            is_effective=True,
        ),
        "shaded": _e(
            shifts_support_rebel=True,
            places_patriot_militia_u=True,
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 26: Josiah Martin, NC Royal Governor
    # U: Place 1 British Fort or 2 Tories in NC
    # S: Patriots free March + Battle in NC
    # ------------------------------------------------------------------
    26: {
        "unshaded": _e(
            places_british_pieces=True,
            is_effective=True,
        ),
        "shaded": _e(
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 27: The Queen's Rangers Show for Battle
    # U: Place 2 Tories (from Unavail/Avail) in each of 2 British-Control Colonies
    # S: Shift 2 Cities toward Active Opposition + place Militia in each
    # ------------------------------------------------------------------
    27: {
        "unshaded": _e(
            places_british_pieces=True,
            is_effective=True,
        ),
        "shaded": _e(
            shifts_support_rebel=True,
            places_patriot_militia_u=True,
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 28: Battle of Moore's Creek Bridge
    # U: Replace every Militia with 2 Tories in one space
    # S: Replace every Tory with 2 Militia in one space
    # ------------------------------------------------------------------
    28: {
        "unshaded": _e(
            places_british_pieces=True,
            is_effective=True,
        ),
        "shaded": _e(
            places_patriot_militia_u=True,
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 29: Edward Bancroft, British Spy
    # U: Activate half of Patriots' or Indians' hidden pieces
    # S: (none)
    # ------------------------------------------------------------------
    29: {
        "unshaded": _e(
            is_effective=True,
        ),
        "shaded": dict(_NONE),
    },
    # ------------------------------------------------------------------
    # Card 30: Hessians
    # U: Place up to 2 Brit Regs in each of 3 spaces, Brit Res +2
    # S: Remove 1 in 5 Brit Regs from map
    # ------------------------------------------------------------------
    30: {
        "unshaded": _e(
            places_british_pieces=True,
            is_effective=True,
        ),
        "shaded": _e(
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 31: Thomas Brown and King's Rangers
    # U: Place 1 British Fort + 2 Tories in SC or GA
    # S: Place 2 Militia in SC/GA + Partisans
    # ------------------------------------------------------------------
    31: {
        "unshaded": _e(
            places_british_pieces=True,
            is_effective=True,
        ),
        "shaded": _e(
            places_patriot_militia_u=True,
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 32: Rule Britannia!
    # U: Place up to 2 Regs + 2 Tories (from Unavail/Avail) in Colony
    # S: Any Faction gets half Cities under Brit Control as Resources
    # ------------------------------------------------------------------
    32: {
        "unshaded": _e(
            places_british_pieces=True,
            is_effective=True,
        ),
        "shaded": _e(
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 33: The Burning of Falmouth
    # U: Patriot Res -3, remove 2 Militia
    # S: Free Rally in 2 spaces adj to Massachusetts, Patriot Res +3
    # ------------------------------------------------------------------
    33: {
        "unshaded": _e(
            is_effective=True,
        ),
        "shaded": _e(
            adds_patriot_resources_3plus=True,
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 34: Lord Sandwich, First Lord of the Admiralty
    # U: Brit Res +6, lower FNI
    # S: Raise FNI, British Ineligible through next card
    # ------------------------------------------------------------------
    34: {
        "unshaded": _e(
            adds_british_resources_3plus=True,
            is_effective=True,
        ),
        "shaded": _e(
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 35: Tryon Plot
    # U: Remove 2 Patriot pieces in NY/NYC, activate Militia
    # S: Remove all Tories in NY or adjacent
    # ------------------------------------------------------------------
    35: {
        "unshaded": _e(
            is_effective=True,
        ),
        "shaded": _e(
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 36: Naval Battle in West Indies
    # U: French remove 3 French Regs to Available, lower FNI
    # S: British remove 4 Brit Regs from WI to Available
    # ------------------------------------------------------------------
    36: {
        "unshaded": _e(
            is_effective=True,
        ),
        "shaded": _e(
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 37: The Armada of 1779
    # U: Patriot Res -2, French Res -3, lower FNI
    # S: Remove 4 Brit Regs from map, raise FNI
    # ------------------------------------------------------------------
    37: {
        "unshaded": _e(
            is_effective=True,
        ),
        "shaded": _e(
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 38: Johnson's Royal Greens
    # U: Place 4 British cubes in Quebec or NY (Unavail/Avail), Brit Eligible
    # S: Place 3 Militia or 3 WP in NY
    # ------------------------------------------------------------------
    38: {
        "unshaded": _e(
            places_british_pieces=True,
            is_effective=True,
        ),
        "shaded": _e(
            places_patriot_militia_u=True,  # can place Militia
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 39: "His Majesty, King Mob"
    # U: Shift 3 Cities toward Neutral
    # S: (none)
    # ------------------------------------------------------------------
    39: {
        "unshaded": _e(
            # toward Neutral — NOT toward royalist or rebel
            is_effective=True,
        ),
        "shaded": dict(_NONE),
    },
    # ------------------------------------------------------------------
    # Card 40: Battle of the Chesapeake
    # U: FNI to 0, Brit Res +2
    # S: FNI to 3
    # ------------------------------------------------------------------
    40: {
        "unshaded": _e(
            is_effective=True,
        ),
        "shaded": _e(
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 41: William Pitt: America Can't Be Conquered
    # U: Shift 2 Colonies toward Passive Support
    # S: Shift 2 Colonies toward Passive Opposition
    # ------------------------------------------------------------------
    41: {
        "unshaded": _e(
            shifts_support_royalist=True,
            is_effective=True,
        ),
        "shaded": _e(
            shifts_support_rebel=True,
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 42: British Attack Danbury
    # U: Patriot Res -3, place 1 Tory in CT
    # S: Place 3 Militia + 1 Continental in CT
    # ------------------------------------------------------------------
    42: {
        "unshaded": _e(
            places_british_pieces=True,
            is_effective=True,
        ),
        "shaded": _e(
            places_patriot_militia_u=True,
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 43: HMS Russian Merchant
    # U: In up to 3 spaces w/ Brit Reg, add up to 2 Tories (Avail/Unavail)
    # S: Remove 1 in 3 Tories
    # ------------------------------------------------------------------
    43: {
        "unshaded": _e(
            places_british_pieces=True,
            is_effective=True,
        ),
        "shaded": _e(
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 44: Earl of Mansfield Recalled From Paris
    # U: Any 1 Faction Ineligible through next card
    # S: (none)
    # ------------------------------------------------------------------
    44: {
        "unshaded": _e(
            is_effective=True,
        ),
        "shaded": dict(_NONE),
    },
    # ------------------------------------------------------------------
    # Card 45: Adam Smith ~ Wealth of Nations
    # U: Brit Res +6
    # S: Brit Res -4
    # ------------------------------------------------------------------
    45: {
        "unshaded": _e(
            adds_british_resources_3plus=True,
            is_effective=True,
        ),
        "shaded": _e(
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 46: Edmund Burke on Conciliation
    # U: Place 1 Tory (Unavail/Avail) in each of 3 spaces
    # S: Shift 2 Cities toward Passive Opposition
    # ------------------------------------------------------------------
    46: {
        "unshaded": _e(
            places_british_pieces=True,
            is_effective=True,
        ),
        "shaded": _e(
            shifts_support_rebel=True,
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 47: Tories Tested
    # U: Place 3 Tories in Colony w/ British Control
    # S: Replace Tories with Militia in Colony + Propaganda
    # ------------------------------------------------------------------
    47: {
        "unshaded": _e(
            places_british_pieces=True,
            is_effective=True,
        ),
        "shaded": _e(
            places_patriot_militia_u=True,
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 48: God Save the King
    # U: British free March + may free Battle
    # S: Non-British Faction moves units from 3 spaces w/ Brit Regs
    # ------------------------------------------------------------------
    48: {
        "unshaded": _e(
            is_effective=True,
        ),
        "shaded": _e(
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 49: Claude Louis, Comte de Saint-Germain
    # U: Move 5 French Regs from Available to Unavailable
    # S: Move 5 French Regs from Unavailable to Available
    # ------------------------------------------------------------------
    49: {
        "unshaded": _e(
            is_effective=True,
        ),
        "shaded": _e(
            places_french_from_unavailable=True,
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 50: Admiral d'Estaing
    # U: French Ineligible through next card, remove 2 French Regs to Avail
    # S: Place 2 Continentals + 2 French Regs (from Avail or WI) in Colony
    # ------------------------------------------------------------------
    50: {
        "unshaded": _e(
            is_effective=True,
        ),
        "shaded": _e(
            places_french_on_map=True,
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 51: Bermuda Gunpowder Plot
    # U: British free March + Battle, -2 Attacker Loss
    # S: Patriots free March + Battle, +2 Defender Loss
    # ------------------------------------------------------------------
    51: {
        "unshaded": _e(
            is_effective=True,
        ),
        "shaded": _e(
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 52: French Fleet Arrives in Wrong Spot
    # U: Remove up to 4 French Regs from map, free Battle w/ +2 FL
    # S: (none)
    # ------------------------------------------------------------------
    52: {
        "unshaded": _e(
            is_effective=True,
        ),
        "shaded": dict(_NONE),
    },
    # ------------------------------------------------------------------
    # Card 53: French Ports Accept Patriot's Ships
    # U: Brit Res +3, lower FNI 2
    # S: Brit Res -2, Patriot Res +2, raise FNI
    # ------------------------------------------------------------------
    53: {
        "unshaded": _e(
            adds_british_resources_3plus=True,
            is_effective=True,
        ),
        "shaded": _e(
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 54: Antoine de Sartine
    # U: Move 1 Squadron/Blockade from WI to Unavailable
    # S: Move 2 Squadrons/Blockades from Unavailable to WI
    # ------------------------------------------------------------------
    54: {
        "unshaded": _e(
            is_effective=True,
        ),
        "shaded": _e(
            places_french_from_unavailable=True,  # Squadrons from Unavail
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 55: French Navy Dominates Caribbean
    # U: Move 3 French Regs map→WI, free Battle in WI, lower FNI
    # S: Move 4 Brit Regs map→WI, British must Battle there
    # ------------------------------------------------------------------
    55: {
        "unshaded": _e(
            is_effective=True,
        ),
        "shaded": _e(
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 56: Jacques Turgot's Economic Liberalism
    # U: Patriot Res -3
    # S: Patriot Res +3
    # ------------------------------------------------------------------
    56: {
        "unshaded": _e(
            is_effective=True,
        ),
        "shaded": _e(
            adds_patriot_resources_3plus=True,
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 57: French Fleet Sails for the Caribbean
    # U: Move 2 French Regs Avail→WI, French Ineligible, lower FNI
    # S: Move 2 Brit Regs map→WI, British Ineligible
    # ------------------------------------------------------------------
    57: {
        "unshaded": _e(
            is_effective=True,
        ),
        "shaded": _e(
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 58: Marquis de Lafayette Arrives in Colonies
    # U: Patriot Res -4
    # S: In NY, Quebec, NW replace Tories with Patriot Militia
    # ------------------------------------------------------------------
    58: {
        "unshaded": _e(
            is_effective=True,
        ),
        "shaded": _e(
            places_patriot_militia_u=True,
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 59: Tronson de Coudray
    # U: Remove 2 Cont + 2 French Regs from one space to Available
    # S: Patriot Res +3
    # ------------------------------------------------------------------
    59: {
        "unshaded": _e(
            is_effective=True,
        ),
        "shaded": _e(
            adds_patriot_resources_3plus=True,
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 60: Comte d'Orvilliers Builds a Fleet
    # U: Lower FNI 2, French Res -4
    # S: Raise FNI, Brit Res -3
    # ------------------------------------------------------------------
    60: {
        "unshaded": _e(
            is_effective=True,
        ),
        "shaded": _e(
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 61: Minister Comte de Vergennes
    # U: Patriots Ineligible through next card
    # S: Patriot Res +3, French Res +2
    # ------------------------------------------------------------------
    61: {
        "unshaded": _e(
            is_effective=True,
        ),
        "shaded": _e(
            adds_patriot_resources_3plus=True,
            adds_french_resources=True,
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 62: Charles Michel de Langlade
    # U: Place 3 WP or 3 Tories in NY, Quebec, or NW
    # S: Place 3 French Regs in Quebec or 3 Militia in NW
    # ------------------------------------------------------------------
    62: {
        "unshaded": _e(
            places_village=False,
            places_british_pieces=True,  # can place Tories
            is_effective=True,
        ),
        "shaded": _e(
            places_french_on_map=True,
            places_patriot_militia_u=True,  # can place Militia
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 63: French and Spanish Besiege Gibraltar
    # U: Brit Res +1, lower FNI, remove 2 Brit Regs from WI to Avail
    # S: Brit Res -5
    # ------------------------------------------------------------------
    63: {
        "unshaded": _e(
            is_effective=True,
        ),
        "shaded": _e(
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 64: The Affair of Fielding and Bylandt
    # U: Brit Res +3, lower FNI
    # S: Patriot Res +5
    # ------------------------------------------------------------------
    64: {
        "unshaded": _e(
            adds_british_resources_3plus=True,
            is_effective=True,
        ),
        "shaded": _e(
            adds_patriot_resources_3plus=True,
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 65: Jacques Necker, Finance Minister
    # U: French Res -4
    # S: French Res +3
    # ------------------------------------------------------------------
    65: {
        "unshaded": _e(
            is_effective=True,
        ),
        "shaded": _e(
            adds_french_resources=True,
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 66: Don Bernardo Takes Pensacola
    # U: Place 6 British cubes in FL or SW
    # S: French/Patriots free March + Battle in FL (+2 FL)
    # ------------------------------------------------------------------
    66: {
        "unshaded": _e(
            places_british_pieces=True,
            is_effective=True,
        ),
        "shaded": _e(
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 67: De Grasse Arrives with French Fleet
    # U: Lower FNI, remove 3 French Regs from WI to Available
    # S: French/Patriots free Rally/Muster, remain Eligible
    # ------------------------------------------------------------------
    67: {
        "unshaded": _e(
            is_effective=True,
        ),
        "shaded": _e(
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 68: French in America Want Canada
    # U: Relocate up to 6 cubes to Quebec + place Fort
    # S: (none)
    # ------------------------------------------------------------------
    68: {
        "unshaded": _e(
            is_effective=True,
        ),
        "shaded": dict(_NONE),
    },
    # ------------------------------------------------------------------
    # Card 69: Admiral Pierre André de Suffren
    # U: Lower FNI 2, Brit Res +2
    # S: Raise FNI, French Res +3
    # ------------------------------------------------------------------
    69: {
        "unshaded": _e(
            is_effective=True,
        ),
        "shaded": _e(
            adds_french_resources=True,
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 70: British Gain From French in India
    # U: Remove 3 Regulars from map/WI to Available
    # S: (none)
    # ------------------------------------------------------------------
    70: {
        "unshaded": _e(
            is_effective=True,
        ),
        "shaded": dict(_NONE),
    },
    # ------------------------------------------------------------------
    # Card 71: Treaty of Amity and Commerce
    # U: Add pop of Rebellion-Control Cities to Patriot Resources
    # S: French Res +5
    # ------------------------------------------------------------------
    71: {
        "unshaded": _e(
            adds_patriot_resources_3plus=True,  # can be 3+ depending on cities
            is_effective=True,
        ),
        "shaded": _e(
            adds_french_resources=True,
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 72: French Settlers Help
    # U: Place 1 Fort/Village + 3 Militia/WP/cubes in Indian Reserve Prov
    # S: (none)
    # ------------------------------------------------------------------
    72: {
        "unshaded": _e(
            places_village=True,
            is_effective=True,
        ),
        "shaded": dict(_NONE),
    },
    # ------------------------------------------------------------------
    # Card 73: Sullivan Expedition vs Iroquois and Tories
    # U: Remove 1 Fort or Village in NY, NW, or Quebec
    # S: (none)
    # ------------------------------------------------------------------
    73: {
        "unshaded": _e(
            removes_patriot_fort=True,  # can remove Patriot Fort
            removes_village=True,       # can remove Village
            is_effective=True,
        ),
        "shaded": dict(_NONE),
    },
    # ------------------------------------------------------------------
    # Card 74: Chickasaw Ally with British
    # U: Indians/British add 1 Res per 2 Villages
    # S: In 2 spaces remove WP + Militia
    # ------------------------------------------------------------------
    74: {
        "unshaded": _e(
            is_effective=True,
        ),
        "shaded": _e(
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 75: Congress' Speech to the Six Nations
    # U: Indians free Gather in 3 Indian Reserve Provs + free War Path
    # S: Remove 3 Indian pieces from NW (Villages last)
    # ------------------------------------------------------------------
    75: {
        "unshaded": _e(
            grants_free_gather=True,
            is_effective=True,
        ),
        "shaded": _e(
            removes_village=True,  # can remove Villages
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 76: Edward Hand Raids into Indian Country
    # U: Replace 3 Militia with 3 Tories in Province
    # S: Remove 2 Villages
    # ------------------------------------------------------------------
    76: {
        "unshaded": _e(
            places_british_pieces=True,
            is_effective=True,
        ),
        "shaded": _e(
            removes_village=True,
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 77: General Burgoyne Cracks Down
    # U: Place 1 Village (space w/ British+Indian), WP to Underground
    # S: Remove 1 British piece in 3 Provinces, Raid in each
    # ------------------------------------------------------------------
    77: {
        "unshaded": _e(
            places_village=True,
            is_effective=True,
        ),
        "shaded": _e(
            inflicts_british_casualties=False,  # removes to Available, not Casualties
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 78: Cherry Valley Destroyed by Tories
    # U: Patriots remove 1/4 units on map
    # S: Add 1 Militia in 4 spaces w/ Tory or Indian
    # ------------------------------------------------------------------
    78: {
        "unshaded": _e(
            is_effective=True,
        ),
        "shaded": _e(
            places_patriot_militia_u=True,
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 79: Tuscarora and Oneida Come to Washington
    # U: Place 1 Village + 2 WP in Colony
    # S: Remove 1 Village + 2 WP in Colony
    # ------------------------------------------------------------------
    79: {
        "unshaded": _e(
            places_village=True,
            is_effective=True,
        ),
        "shaded": _e(
            removes_village=True,
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 80: Confusion Allows Slaves to Escape
    # U: 1 Faction removes 2 own pieces in each of 2 spaces
    # S: (none)
    # ------------------------------------------------------------------
    80: {
        "unshaded": _e(
            is_effective=True,
        ),
        "shaded": dict(_NONE),
    },
    # ------------------------------------------------------------------
    # Card 81: Creek and Seminole Active in South
    # U: Place 2 WP + Raid + 1 Village in SC or GA
    # S: Remove 2 WP in SC and/or GA
    # ------------------------------------------------------------------
    81: {
        "unshaded": _e(
            places_village=True,
            is_effective=True,
        ),
        "shaded": _e(
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 82: Frustrated Shawnee Warriors Attack
    # U: Place WP + Raid in VA, GA, NC, SC
    # S: Remove 3 Indian pieces from VA, GA, NC, SC (Villages last)
    # ------------------------------------------------------------------
    82: {
        "unshaded": _e(
            is_effective=True,
        ),
        "shaded": _e(
            removes_village=True,  # can remove Villages
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 83: Guy Carleton and Indians Negotiate
    # U: Shift Quebec City to Active Support, place 2 WP in Quebec
    # S: Place up to 3 pieces (max 1 Fort/Village) in Quebec/Quebec City
    # ------------------------------------------------------------------
    83: {
        "unshaded": _e(
            shifts_support_royalist=True,
            is_effective=True,
        ),
        "shaded": _e(
            places_patriot_fort=True,    # can place Fort
            places_village=True,         # can place Village
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 84: "Merciless Indian Savages"
    # U: Indians free Gather in 2 Colonies
    # S: Remove 1 Village
    # ------------------------------------------------------------------
    84: {
        "unshaded": _e(
            grants_free_gather=True,
            is_effective=True,
        ),
        "shaded": _e(
            removes_village=True,
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 85: Indians Help British Raids on Mississippi
    # U: Place 3 Brit Regs/Tories in SW
    # S: Place 2 Militia/Cont + 2 French Regs in SW
    # ------------------------------------------------------------------
    85: {
        "unshaded": _e(
            places_british_pieces=True,
            is_effective=True,
        ),
        "shaded": _e(
            places_patriot_militia_u=True,
            places_french_on_map=True,
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 86: Stockbridge Indians
    # U: Activate all Militia in Massachusetts or space w/ Indian
    # S: Add 3 Militia in Massachusetts or space w/ Indian
    # ------------------------------------------------------------------
    86: {
        "unshaded": _e(
            is_effective=True,
        ),
        "shaded": _e(
            places_patriot_militia_u=True,
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 87: Patriots Massacre Lenape Indians
    # U: Remove 1 piece in Pennsylvania, Remain Eligible
    # S: (none)
    # ------------------------------------------------------------------
    87: {
        "unshaded": _e(
            is_effective=True,
        ),
        "shaded": dict(_NONE),
    },
    # ------------------------------------------------------------------
    # Card 88: "If it hadn't been so foggy..."
    # U: 1 Faction moves own units from spaces shared w/ that Faction
    # S: (none)
    # ------------------------------------------------------------------
    88: {
        "unshaded": _e(
            is_effective=True,
        ),
        "shaded": dict(_NONE),
    },
    # ------------------------------------------------------------------
    # Card 89: War Damages Colonies' Economy
    # U: Replace 4 Militia/Cont with Tories
    # S: Replace 3 Tories with Patriot Militia
    # ------------------------------------------------------------------
    89: {
        "unshaded": _e(
            places_british_pieces=True,  # replaces with Tories
            is_effective=True,
        ),
        "shaded": _e(
            places_patriot_militia_u=True,
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 90: "The World Turned Upside Down"
    # U: Place 1 friendly Fort or Village
    # S: Remove 2 Brit Regs to Casualties
    # ------------------------------------------------------------------
    90: {
        "unshaded": _e(
            places_village=True,     # can place Village (executing faction)
            is_effective=True,
        ),
        "shaded": _e(
            inflicts_british_casualties=True,
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 91: Indians Help British Outside Colonies
    # U: Place 1 Village + 2 WP in Indian Reserve Province
    # S: Remove 1 Village in Indian Reserve Province
    # ------------------------------------------------------------------
    91: {
        "unshaded": _e(
            places_village=True,
            is_effective=True,
        ),
        "shaded": _e(
            removes_village=True,
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 92: Cherokees Supplied by the British
    # U: Place a second Fort/Village where you have one
    # S: (none)
    # ------------------------------------------------------------------
    92: {
        "unshaded": _e(
            places_village=True,
            is_effective=True,
        ),
        "shaded": dict(_NONE),
    },
    # ------------------------------------------------------------------
    # Card 93: Wyoming Massacre
    # U: Shift up to 3 Colonies adj to Indian Reserve toward Neutral, Raid
    # S: (none)
    # ------------------------------------------------------------------
    93: {
        "unshaded": _e(
            # Toward Neutral — not specifically royalist or rebel
            is_effective=True,
        ),
        "shaded": dict(_NONE),
    },
    # ------------------------------------------------------------------
    # Card 94: Herkimer's Relief Column
    # U: Indians free Gather + Tories free Muster in NY, remove Militia
    # S: Remove 4 WP in/adjacent to PA
    # ------------------------------------------------------------------
    94: {
        "unshaded": _e(
            grants_free_gather=True,
            places_british_pieces=True,  # Tories free Muster
            is_effective=True,
        ),
        "shaded": _e(
            is_effective=True,
        ),
    },
    # ------------------------------------------------------------------
    # Card 95: Ohio Country Frontier Erupts
    # U: In NW remove enemy Fort/Village + place 3 friendly units
    # S: (none)
    # ------------------------------------------------------------------
    95: {
        "unshaded": _e(
            removes_patriot_fort=True,  # can remove enemy Fort
            removes_village=True,       # can remove Village
            is_effective=True,
        ),
        "shaded": dict(_NONE),
    },
    # ------------------------------------------------------------------
    # Card 96: Iroquois Confederacy
    # U: Indians free Gather + War Path in 2 Indian Reserve Provinces
    # S: Remove 1 Indian Village
    # ------------------------------------------------------------------
    96: {
        "unshaded": _e(
            grants_free_gather=True,
            is_effective=True,
        ),
        "shaded": _e(
            removes_village=True,
            is_effective=True,
        ),
    },
}
