# Card audit (before fixes)

Source: `Reference Documents/card reference full.txt`
Scope: Cards 2, 6, 24, 28, 29, 32

- **Card 2 – Common Sense**: Implementation hardcodes Boston for unshaded and New York City/Philadelphia for shaded instead of selecting any one/two Cities.
- **Card 6 – Benedict Arnold**: Implementation hardcodes Virginia and only removes Underground Militia; should target any one Colony and remove Fort + 2 Militia (Underground then Active) regardless of status.
- **Card 24 – Declaration of Independence**: Unshaded/Shaded effects are inverted vs reference; current code places pieces instead of removing them.
- **Card 28 – Battle of Moore’s Creek Bridge**: Target is locked to North Carolina instead of any one space; function body is mis-indented with `target` defined at module scope.
- **Card 29 – Edward Bancroft, British Spy**: Handler contains stray text and deterministically targets Patriots; needs selectable faction (Patriots or Indians) per reference.
- **Card 32 – Rule Britannia!**: Unshaded locked to Virginia; shaded always gives Resources to Patriots; both should allow any Colony and any faction for Resources.
