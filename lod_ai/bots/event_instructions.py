# lod_ai/bots/event_instructions.py
# ------------------------------------------------------------
# Brown-Bess musket instructions for Non-Player Event choices
# ------------------------------------------------------------

BRITISH = {
    18: "force_if_eligible_enemy",  # "If it hadn't been so stormy…" — target eligible enemy, else C&SA
    23: "force",                    # Lt Col Francis Marion
    29: "ignore_if_4_militia",      # Edward Bancroft, British Spy
    # 30 (Hessians): the sheet entry is EXECUTION guidance for when an
    # ENEMY plays the shaded text ("leave 1 Regular per space"), not a
    # play condition — handled in evt_030; the old "force" here was a
    # layer error (audit Session 28; fixed Session 47).  "normal" keeps
    # the musket-icon key (data invariant) while falling through to the
    # standard B2 evaluation.
    30: "normal",                   # Hessians — execution guidance only
    44: "force_if_eligible_enemy",  # Earl of Mansfield Recalled — target eligible enemy, else C&SA
    51: "force_if_51",              # Bermuda Gunpowder Plot — March to set up Battle, else C&SA
    52: "force_if_52",              # French Fleet Wrong Spot — March to set up Battle, else C&SA
    62: "force_if_62",              # Charles Michel de Langlade — NY Active Opp w/o Tories, else C&SA
    70: "force_if_70",              # British Gain From French in India — French Regs to remove, else C&SA
    80: "force_if_80",              # Confusion Allows Slaves to Escape — Rebel pieces in Cities, else C&SA
    88: "force",                    # "If it hadn't been so foggy…"
    95: "force",                    # Ohio Country Frontier Erupts
}

# Additional musket instructions for the other factions.  These are a
# pared‑down version of the Brown‑Bess chart used by the simplified bots.

PATRIOTS = {
    8: "force_if_french_not_human",   # Culper Spy Ring — skip if French is human
    18: "force_if_eligible_enemy",    # "If it hadn't been so stormy…" — target eligible enemy, else C&SA
    29: "force",                      # Edward Bancroft, British Spy — target Indians
    44: "force_if_eligible_enemy",    # Earl of Mansfield Recalled from Paris — target eligible enemy, else C&SA
    51: "force_if_51",                 # Bermuda Gunpowder Plot — March to set up Battle; if not possible, C&SA
    52: "force_if_52",                  # French Fleet Arrives in the Wrong Spot — select space per Battle, else ignore
    70: "force",                      # British Gain From French in India
    71: "force_unshaded",             # Treaty of Amity and Commerce — use unshaded text
    80: "force_if_80",                # Confusion Allows Slaves to Escape — errata: Village removable, else C&SA
    83: "force",                      # Guy Carleton and Indians Negotiate
    86: "force",                      # Stockbridge Indians
    88: "force",                      # "If it hadn't been so foggy…"
    90: "force_unshaded",             # "The World Turned Upside Down" — use unshaded text
}

# (Card 86 Stockbridge Indians previously had an INDIANS entry, but the
# reference ICON line is "P – Musket" only — Indians have no 8.3.1
# instructions there and follow their flowchart. The entry was unreachable
# anyway: base_bot consults these dicts only when the faction's symbol
# carries the Musket icon. Removed Session 24.)
INDIANS = {
    4: "force_shaded",    # The Penobscot Expedition — "Use the shaded text." (conditional in IndianBot override)
    18: "force_if_eligible_enemy",   # "If it hadn't been so stormy…" — target eligible enemy, else C&SA
    21: "force",   # The Gamecock Thomas Sumter
    22: "force",   # The Newburgh Conspiracy
    29: "force",   # Edward Bancroft, British Spy
    32: "force_shaded",   # Rule Britannia! — "Use the shaded text."
    38: "force_shaded",   # Johnson's Royal Greens — "Use the shaded text." (WP condition in IndianBot override)
    44: "force_if_eligible_enemy",   # Earl of Mansfield — target eligible enemy, else C&SA
    70: "force",   # British Gain From French in India
    72: "force",   # French Settlers Help (village condition in IndianBot override)
    80: "force_if_80",   # Confusion Allows Slaves to Escape — errata: Patriot Fort removable, else C&SA
    83: "force",   # Guy Carleton and Indians Negotiate (special handling in IndianBot override)
    88: "force",   # "If it hadn't been so foggy…"
    89: "force",   # War Damages Colonies' Economy
    90: "force",   # "The World Turned Upside Down" (village condition in IndianBot override)
}

FRENCH = {
    52: "force_if_52",  # French Fleet: Remove no French Regulars. If no Battle space, Command & SA
    62: "force_if_62",  # Langlade: Place Militia only. If not possible, Command & SA
    70: "force_if_70",  # British Gain: Remove Brit Regs from rebel spaces. If none, Command & SA
    73: "force_if_73",  # Sullivan: If no British Fort removed, Command & SA
    83: "force_if_83",  # Carleton: Select Quebec City. If no Rebellion gain, Command & SA
    88: "force",        # "If it hadn't been so foggy…"
    89: "force",        # War Damages Colonies' Economy — Select Active Support spaces first
    95: "force_if_95",  # Ohio Frontier: If no British Fort removed, Command & SA
}
