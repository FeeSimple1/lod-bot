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
