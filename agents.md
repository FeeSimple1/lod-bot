# AGENTS.md
Repository Guidelines
=====================

1. **Keep the repo clean**
   - Remove all tracked `__pycache__` directories and `*.pyc` files.
   - Add a `.gitignore` in the project root that excludes `__pycache__/` and `*.pyc`.

2. **Deduplicate reference materials**
   - Only keep a single copy of files such as `map_base.csv` and `rules_consts.py`. Files in the Reference Documents folder do not count as duplicates.

3. **Clean up stray artifacts**
   - Search for `:contentReference[` and lines containing shell prompts (e.g. `root@...`) in source files.
     Remove these artifacts or convert them into normal comments to keep the code readable.

4. **Testing**
   - Ensure `pytest -q` runs successfully before committing changes.
     If dependencies are missing, consult project maintainers for setup instructions.

5. **Documentation**
   - Update the README if file paths or other usage details change.

6. **Source of Truth**
   - The documents in the Reference Documents folder are to be used as the source of truth.
     All documents in the data and lod_ai folder must not conflict with them.
   - `rules_consts.py` is also a source of truth; no labels for spaces or any other game item that is not permitted by rules_consts.py is allowed to be used.
   - None of the source-of-truth files are to be changed; other files must be changed to be consistent with them.
   - No file in the Reference Documents folder may be deleted, even if it is a duplicate of files located elsewhere.
   - For card behavior and card text, `Reference Documents/card reference full.txt` is the source of truth.

7. **No guessing; ask when unsure**
   - Do not invent card meanings, target selection rules, or “reasonable” interpretations.
   - If implementation is ambiguous or the engine lacks a needed hook, STOP and ask the user specific questions instead of guessing.
   - Record all such questions in a repo file named `QUESTIONS.md` (create it if missing), then stop work until answered.

8. **Cards: required workflow**
   - When updating card handlers in `lod_ai/cards/`:
     1) First produce an audit report of mismatches vs `Reference Documents/card reference full.txt` (no edits).
     2) Then apply fixes, keeping edits scoped to `lod_ai/cards/` unless a shared helper is strictly required.
     3) Add/adjust validation so future mismatches are caught by tests.
   - Summarize changes by card number and filename.

Follow these guidelines for future contributions.


