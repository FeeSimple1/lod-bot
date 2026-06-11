"""Input provider that answers Liberty or Death CLI prompts with a policy."""
from __future__ import annotations

from typing import Optional

from .observation import serialize_state


class LLMInputProvider:
    """Bridges the CLI's menu prompts to a decision Policy.

    Installed via ``cli_utils.set_input_provider``.  During an LLM faction's
    turn the existing wizards call ``prompt`` for each sub-decision; we render
    the board for the acting faction and ask the policy to pick.  A retry guard
    prevents an ill-behaved policy from looping forever on one prompt.
    """

    def __init__(self, policy, engine, llm_factions, *, verbose: bool = False,
                 max_retries: int = 12, policies: Optional[dict] = None):
        self.policy = policy
        self.policies = {k.upper(): v for k, v in (policies or {}).items()}
        self.engine = engine
        self.llm_factions = set(llm_factions)
        self.verbose = verbose
        self.max_retries = max_retries
        self.current_faction: Optional[str] = None
        self._last_sig = None
        self._repeat = 0
        self.decisions = 0

    def policy_for(self, faction: Optional[str]):
        """Per-faction policy when a mapping was provided, else the shared one."""
        if faction and self.policies:
            return self.policies.get(faction.upper(), self.policy)
        return self.policy

    def begin_turn(self, faction: str, card: dict, allowed: dict) -> None:
        self.current_faction = faction
        self._last_sig = None
        self._repeat = 0
        # Let stateful policies reset per-turn bookkeeping (optional hook).
        hook = getattr(self.policy, "begin_turn", None)
        if callable(hook):
            hook(faction, card, allowed)

    def prompt(self, label: str, menu) -> str:
        # Track repeated identical prompts (means the last answer was rejected).
        sig = (label, str(menu))
        self._repeat = self._repeat + 1 if sig == self._last_sig else 0
        self._last_sig = sig

        # Safety valve: after too many rejections, force a guaranteed-legal pick.
        if self._repeat >= self.max_retries:
            from .policy import _valid_choices
            choices = _valid_choices(menu)
            return choices[0] if choices else ""

        obs = serialize_state(self.engine.state, self.current_faction)
        pol = self.policy_for(self.current_faction)
        try:
            ans = pol.choose(obs, label, menu, self.current_faction)
        except Exception as exc:  # pragma: no cover
            if self.verbose:
                print(f"[LLMInputProvider] policy error: {exc}")
            from .policy import _valid_choices
            choices = _valid_choices(menu)
            ans = choices[0] if choices else ""
        self.decisions += 1
        if self.verbose:
            print(f"[LLM:{self.current_faction}] {label!r} -> {ans!r}")
        return str(ans)
