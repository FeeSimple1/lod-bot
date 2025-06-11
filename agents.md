# AGENTS.md
Repository Guidelines
=====================

1. **Keep the repo clean**
   - Remove all tracked `__pycache__` directories and `*.pyc` files.
   - Add a `.gitignore` in the project root that excludes `__pycache__/` and `*.pyc`.

2. **Deduplicate reference materials**
   - Only keep a single copy of files such as `map_base.csv` and `rules_consts.py`.  
     Decide whether to use `data/` or `Reference Documents/` as the canonical location.

3. **Clean up stray artifacts**
   - Search for `:contentReference[` and lines containing shell prompts (e.g. `root@...`) in source files.  
     Remove these artifacts or convert them into normal comments to keep the code readable.

4. **Testing**
   - Ensure `pytest -q` runs successfully before committing changes.  
     If dependencies are missing, consult project maintainers for setup instructions.

5. **Documentation**
   - Update the README if file paths or other usage details change.
  
6.  **Source of Truth**
   - The documents in the Reference Documents folder are to be used as the source of truth.  All documents in the data and lod_ai folder must not conflict with them.  rules_consts.py is also a source of truth; all unit abbreviations must match those provided in rules_consts.py.  None of these files are to be changed; other files must be changed to be consistent with the files in the Reference Documents folder and with rules_consts.py.  No file in the Reference Documents folder may be deleted, even if it is a duplicate of files located elsewhere.

Follow these guidelines for future contributions.
