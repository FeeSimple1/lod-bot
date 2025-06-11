# rules_consts.py  — Milestone 0 canonical vocabulary
# ---------------------------------------------------
# Track caps & global limits
MAX_RESOURCES = 50
MIN_RESOURCES = 0
MAX_FNI       = 3           # British French Naval Intercept, rule 1.9
MAX_FORT_BRI  = 6
MAX_FORT_PAT  = 6
MAX_VILLAGE   = 12

# Aliases used throughout the codebase
MAX_BRI_FORTS     = MAX_FORT_BRI
MAX_PAT_FORTS     = MAX_FORT_PAT
MAX_IND_VILLAGES  = MAX_VILLAGE
MAX_VP_DIFF   = 25          # auto-win margin

# ---------------------------------------------------
# Faction identifiers (canonical strings everywhere)
BRITISH  = "BRITISH"
PATRIOTS = "PATRIOTS"
INDIANS  = "INDIANS"
FRENCH   = "FRENCH"
# ---------------------------------------------------

# Support / Opposition levels
ACTIVE_SUPPORT       =  2
PASSIVE_SUPPORT      =  1
NEUTRAL              =  0
PASSIVE_OPPOSITION   = -1
ACTIVE_OPPOSITION    = -2

# Piece tags (expanded)
REGULAR_BRI    = "British_Regular"
REGULAR_FRE    = "French_Regular"
REGULAR_PAT    = "Patriot_Continental"
TORY           = "British_Tory"
MILITIA_A      = "Patriot_Militia_A"   # Active
MILITIA_U      = "Patriot_Militia_U"   # Underground
WARPARTY_A     = "Indian_WP_A"
WARPARTY_U     = "Indian_WP_U"
FRENCH_UNAVAIL = "French_Regular_Unavailable"
BRIT_UNAVAIL   = "British_Regular_Unavailable"
TORY_UNAVAIL   = "British_Tory_Unavailable"
FORT_BRI       = "British_Fort"    
FORT_PAT       = "Patriot_Fort"     
VILLAGE        = "Village"
SQUADRON       = "Squadron"
BLOCKADE       = "Blockade"

WINTER_QUARTERS_CARDS = {97, 98, 99, 100, 101, 102, 103, 104}
BRILLIANT_STROKE_CARDS = {105, 106, 107, 108, 109}  # also from reference

# ---------------------------------------------------
# NEW piece-cap constants (§ 1.2, Scenario Setup)
# ---------------------------------------------------
MAX_REGULAR_BRI       = 25
MAX_TORY              = 25
MAX_REGULAR_FRE       = 15
MAX_REGULAR_PAT       = 20
MAX_MILITIA           = 15
MAX_WAR_PARTY         = 15

# --------------------------------------------------------------------------- #
#  West Indies helpers                                                        #
# --------------------------------------------------------------------------- #
WEST_INDIES_ID        = "West_Indies"
MAX_WI_SQUADRONS      = 3     # Rule 4.5 & 6.2 notes

# ---------------------------------------------------
# Marker & token caps
# ---------------------------------------------------
MAX_PROPAGANDA = 12          # §3.3.4 Rabble-Rousing
PROPAGANDA     = "Propaganda"
MAX_RAID = 12            # §3.4.4 Raid
RAID     = "Raid"
BLOCKADE = "blockade"          # used in naval_pressure SA


# For flow-chart calls that say “Play Event” without specifying a side:
DEFAULT_EVENT_SIDE = {
    "British" : False,   # unshaded
    "Indians" : False,   # unshaded
    "Patriots": True,    # shaded
    "French"  : True,    # shaded
}

LEADERS = [
    "LEADER_WASHINGTON",
    "LEADER_ROCHAMBEAU",
    "LEADER_LAUZUN",
    "LEADER_GAGE",
    "LEADER_HOWE",
    "LEADER_CLINTON",
    "LEADER_BRANT",
    "LEADER_CORNPLANTER",
    "LEADER_DRAGGING_CANOE",
]

# Individual leader tags (for convenience)
LEADER_ROCHAMBEAU = "LEADER_ROCHAMBEAU"

# Leader-change progression (Rule 6.5.1)
LEADER_CHAIN = {
    # British
    "LEADER_GAGE":            "LEADER_HOWE",
    "LEADER_HOWE":            "LEADER_CLINTON",
    # French   (active only after Treaty of Alliance)
    "LEADER_ROCHAMBEAU":      "LEADER_LAUZUN",
    # Indians
    "LEADER_BRANT":           "LEADER_CORNPLANTER",
    "LEADER_CORNPLANTER":     "LEADER_DRAGGING_CANOE",
    # Patriots have no changes
}

