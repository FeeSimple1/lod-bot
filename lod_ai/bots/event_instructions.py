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

# Other factions will be filled in as we implement their bots.
PATRIOT: dict[int, str] = {}
INDIAN:  dict[int, str] = {}
FRENCH:  dict[int, str] = {}
