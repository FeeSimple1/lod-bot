# CI workflow (manual install required)

`github-ci.yml` is the GitHub Actions workflow for this repo: full test
suite, the bot clean-sweep gate (`clean_sweep_gate --seeds 1-20`), and the
balance guardrail (`balance_smoke --seeds 1-20`).

It lives here instead of `.github/workflows/` because the automation token
used for pushes lacks the `workflow` scope. To activate CI, copy this file
to `.github/workflows/ci.yml` via the GitHub web UI (Add file -> Create new
file) or push it with a token that has the `workflow` scope.
