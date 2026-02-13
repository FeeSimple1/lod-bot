# Card Audit Report

Source: `Reference Documents/card reference full.txt`
Last updated: Phase 2 compliance audit

---

## FIXED issues (this audit pass)

### late_war.py

- **Card 1 (Waxhaws)**: Fixed shaded "shift toward Neutral" — was shifting -1 (toward Opposition), now correctly shifts toward 0.
- **Card 7 (John Paul Jones)**: Fixed unshaded to allow West Indies OR any City as destination per reference.
- **Card 16 (Mercy Warren)**: Fixed unshaded to allow any target (was hardcoded NYC); fixed shaded to allow any City (was hardcoded Boston).
- **Card 18 ("If it hadn't been so stormy…")**: Fixed `ineligible_next` → `ineligible_through_next`; added shaded no-op (reference says "(none)"); allow any faction selection.
- **Card 19 (Nathan Hale)**: Fixed shaded to place 3 Militia "anywhere" (was hardcoded Pennsylvania).
- **Card 21 (Gamecock Sumter)**: Fixed to allow South Carolina or Georgia target per reference.
- **Card 22 (Newburgh Conspiracy)**: Fixed shaded to mark immediate Tory Desertion per "Immediately execute" in reference.
- **Card 25 (British Prison Ships)**: Fixed both paths to properly shift "toward Passive Support/Opposition" (one step toward target, not set to target); use map helpers for city selection.
- **Card 31 (Thomas Brown)**: Fixed to allow South Carolina or Georgia per reference.
- **Card 39 (King Mob)**: Fixed "shift toward Neutral" — was always -1, now correctly shifts toward 0; use map helpers for city detection.
- **Card 48 (God Save the King)**: Fixed shaded — was using string prefix matching and moving to "available" (removing pieces); now properly moves non-British units to adjacent spaces.
- **Card 57 (French Caribbean)**: Fixed `ineligible_next` → `ineligible_through_next` for both paths; fixed shaded to move British from map to West Indies.
- **Card 62 (Langlade)**: Fixed unshaded to allow War Party OR Tory choice in NY/Quebec/NW per reference; fixed shaded to allow French in Quebec OR Militia in NW.
- **Card 64 (Fielding & Bylandt)**: **Critical fix** — shaded was British -3 & FNI +1, should be Patriots +5 per reference.
- **Card 66 (Don Bernardo)**: Fixed unshaded to allow British cube mix (Regulars + Tories) and Florida or Southwest target.
- **Card 73 (Sullivan)**: Fixed loop structure; added FORT_PAT to removal candidates; added shaded no-op.
- **Card 79 (Tuscarora & Oneida)**: Fixed target to any Colony (was hardcoded Pennsylvania).
- **Card 81 (Creek & Seminole)**: Fixed to allow SC or GA; shaded removes from both locations; includes Active War Party removal.
- **Card 85 (Mississippi Raids)**: Fixed unshaded to allow Regulars and/or Tories mix; shaded allows Militia or Continental choice.
- **Card 87 (Lenape)**: Fixed to remove any piece type (was only War Party); added Remain Eligible logic.
- **Card 94 (Herkimer)**: Fixed shaded to remove from Pennsylvania AND adjacent spaces per reference.
- **Card 95 (Ohio Frontier)**: Added shaded no-op check (was executing for both sides).
- **Card 96 (Iroquois)**: Fixed unshaded to constrain Gather/War Path to Indian Reserve Provinces.

### middle_war.py

- **Card 59 (Tronson de Coudray)**: Fixed to prefer spaces with both Continentals AND French Regulars for the "from one space" requirement.
- **Card 71 (Treaty of Amity)**: **Critical fix** — shaded was British +4, should be French +5; unshaded was dividing population by 3 and capping at 5 and adding to both Patriots and French — should add total population of Rebellion cities to Patriots only.

### early_war.py

- **Card 15 (Morgan's Rifles)**: Fixed shaded to allow any Colony (was hardcoded Virginia).
- **Card 32 (Rule Britannia)**: Fixed sourcing to Unavailable first per "from Unavailable or Available" in reference.
- **Card 33 (Burning of Falmouth)**: Fixed shaded to use adjacency lookup for Massachusetts spaces.
- **Card 35 (Tryon Plot)**: Fixed to allow New York or New York City per reference; shaded allows adjacent space.
- **Card 46 (Edmund Burke)**: Fixed sourcing to Unavailable first per reference.
- **Card 82 (Shawnee Warriors)**: Fixed unshaded provinces — was VA, GA, NY, SC; should be VA, GA, NC, SC (New York → North Carolina per reference).

---

## REMAINING known issues (not yet fixed)

### Brilliant Stroke / Treaty of Alliance (Cards 105-109)
- Not implemented as a true interrupt (no pre-action cancel)
- Does not enforce leader involvement in at least one Limited Command
- Trump chain is incomplete
- Eligibility reset ("All Factions to Eligible") not fully implemented
- Treaty of Alliance preparation check may be incomplete

### Control access patterns (Phase 3)
- Several cards still use `sp.get("British_Control")` instead of `state.get("control", {}).get(sid)`:
  - Card 30 (Hessians) unshaded
  - Card 32 (Rule Britannia) shaded
- This is a design pattern issue — `board/control.py` sets both `sp["British_Control"]` boolean flags and `state["control"][sid]` values. Needs Phase 3 refactoring.

### Cards using `sp.get("type")` or `sp.get("population")`
- Card 71 falls back to `sp.get("population")` when map metadata is unavailable in tests
- Some cards rely on space dict properties that should come from map metadata

### Deterministic bot choices
Many cards require player/bot selection that is currently hardcoded or uses alphabetical ordering as a deterministic fallback. These work for automated play but need proper bot intelligence or human menu prompts:
- Card 2 (Common Sense): City selection
- Card 6 (Benedict Arnold): Colony/space selection
- Card 24 (Declaration of Independence): Space selection for placement/removal
- Card 28 (Moore's Creek): Space selection
- Card 80 (Confusion): Faction and space selection

### Cards with queued vs immediate free ops
Several cards queue free operations via `queue_free_op` that the reference text may intend as immediate execution. This depends on the game engine's free-op processing pipeline:
- Card 1 (Waxhaws): shaded March/Battle
- Card 3 (Illinois Campaign): shaded Partisans (currently immediate via direct call — correct)
- Card 21 (Sumter): shaded March/Battle
- Card 48 (God Save the King): unshaded March/Battle
- Card 52 (French Fleet Wrong Spot): unshaded Battle
- Card 66 (Don Bernardo): shaded March/Battle
- Card 67 (De Grasse): shaded Rally/Muster

### Minor issues
- Card 23 (Francis Marion): Unshaded hardcodes SC→GA move direction, doesn't allow NC; shaded doesn't check NC
- Card 36 (Naval Battle WI): Unshaded removes French from anywhere, reference specifies "on map or West Indies" (functionally equivalent if West Indies is a map space)
- Card 50 (D'Estaing): Shaded sources French Regulars only from Available, reference says "from Available or West Indies"
- Card 70 (French India): "Remove three Regulars" — reference doesn't specify whose; code removes British first then French

---

## Previously documented issues (from earlier audit passes)

The following were documented in earlier passes. Many label compliance issues (string literals) were fixed in Phase 1. The functional issues listed above supersede the earlier notes where they overlap.
