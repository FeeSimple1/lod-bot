# lod_ai/bots/event_instructions.py
# ------------------------------------------------------------
# Brown-Bess musket instructions for Non-Player Event choices
# ------------------------------------------------------------

BRITISH = {
    18: "force",                # "If it hadn't been so stormy…" — target eligible enemy
    23: "force",                # Lt Col Francis Marion
    29: "ignore_if_4_militia",  # Edward Bancroft, British Spy
    30: "force",                # Hessians
    44: "force",                # Earl of Mansfield Recalled — target eligible enemy
    51: "force",                # Bermuda Gunpowder Plot — March to set up Battle
    52: "force",                # French Fleet Arrives in the Wrong Spot
    62: "force",                # Charles Michel de Langlade
    70: "force",                # British Gain From French in India
    80: "force",                # Confusion Allows Slaves to Escape
    88: "force",                # "If it hadn't been so foggy…"
    95: "force",                # Ohio Country Frontier Erupts
}

# Additional musket instructions for the other factions.  These are a
# pared‑down version of the Brown‑Bess chart used by the simplified bots.

PATRIOTS = {
    8: "force",   # Culper Spy Ring — skip if French is human (handled at execution)
    18: "force",  # "If it hadn't been so stormy…"
    29: "force",  # Edward Bancroft, British Spy
    44: "force",  # Earl of Mansfield Recalled from Paris
    51: "force",  # Bermuda Gunpowder Plot
    52: "force",  # French Fleet Arrives in the Wrong Spot
    70: "force",  # British Gain From French in India
    71: "force",  # Treaty of Amity and Commerce
    80: "force",  # Confusion Allows Slaves to Escape
    83: "force",  # Guy Carleton and Indians Negotiate
    86: "force",  # Stockbridge Indians
    88: "force",  # "If it hadn't been so foggy…"
    90: "force",  # "The World Turned Upside Down"
}

INDIANS = {
    4: "force",    # The Penobscot Expedition
    18: "force",   # "If it hadn't been so stormy…"
    21: "force",   # The Gamecock Thomas Sumter
    22: "force",   # The Newburgh Conspiracy
    29: "force",   # Edward Bancroft, British Spy
    32: "force",   # Rule Britannia!
    38: "force",   # Johnson's Royal Greens
    44: "force",   # Earl of Mansfield Recalled from Paris
    70: "force",   # British Gain From French in India
    72: "force",   # French Settlers Help
    80: "force",   # Confusion Allows Slaves to Escape
    83: "force",   # Guy Carleton and Indians Negotiate
    88: "force",   # "If it hadn't been so foggy…"
    89: "force",   # War Damages Colonies' Economy
    90: "force",   # "The World Turned Upside Down"
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
