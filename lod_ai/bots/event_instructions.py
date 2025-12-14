# lod_ai/bots/event_instructions.py
# ------------------------------------------------------------
# Brown-Bess musket instructions for Non-Player Event choices
# ------------------------------------------------------------

BRITISH = {
    18: "ignore",               # “If it hadn’t been so stormy…”
    23: "force",                # Lt Col Francis Marion
    29: "ignore_if_4_militia",  # Edward Bancroft, British Spy
    30: "force",                # Hessians
    44: "ignore",               # Earl of Mansfield Recalled
    52: "force",                # French Fleet Arrives in the Wrong Spot
    70: "force",                # British Gain From French in India
    83: "ignore",               # Guy Carleton and Indians Negotiate
    88: "force",                # “If it hadn’t been so foggy…”
    95: "force",                # Ohio Country Frontier Erupts
}

# Additional musket instructions for the other factions.  These are a
# pared‑down version of the Brown‑Bess chart used by the simplified bots.

PATRIOT = {
    # Always attempt to play these Events using the instructions from the
    # reference sheet.
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

INDIAN = {
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
    52: "force",  # French Fleet Arrives in the Wrong Spot
    62: "force",  # Charles Michel de Langlade
    70: "force",  # British Gain From French in India
    73: "force",  # Sullivan Expedition vs Iroquois and Tories
    83: "force",  # Guy Carleton and Indians Negotiate
    88: "force",  # "If it hadn't been so foggy…"
    89: "force",  # War Damages Colonies' Economy
    95: "force",  # Ohio Country Frontier Erupts
}

