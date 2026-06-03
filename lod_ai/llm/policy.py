"""Decision policies for the LLM harness.

A policy answers one menu prompt at a time.  ``choose`` receives the rendered
board observation plus the structured menu, and returns the raw string a human
would have typed (an option number, or a count).
"""
from __future__ import annotations

import os
import random
import re
from typing import List, Optional


class Policy:
    """Base policy interface."""

    def choose(self, observation: str, label: str, menu: Optional[dict],
               faction: Optional[str]) -> str:
        raise NotImplementedError


def _valid_choices(menu: Optional[dict]) -> List[str]:
    """Return the set of valid raw responses for a menu."""
    if not menu:
        return []
    if menu.get("kind") == "select":
        n = len(menu.get("options", []))
        choices = [str(i) for i in range(1, n + 1)]
        if menu.get("allow_back"):
            choices.append("0")
        return choices
    if menu.get("kind") == "count":
        lo, hi = menu.get("min", 0), menu.get("max", 0)
        return [str(i) for i in range(lo, hi + 1)]
    return []


class RandomPolicy(Policy):
    """Pick a uniformly random *legal* answer.  Great for smoke-testing the
    harness end-to-end without any model call."""

    def __init__(self, seed: int = 0):
        self.rng = random.Random(seed)

    def choose(self, observation, label, menu, faction):
        choices = _valid_choices(menu)
        if choices:
            return self.rng.choice(choices)
        return ""  # free-text / unknown prompt -> accept default


class ScriptedPolicy(Policy):
    """Replay a fixed list of answers (then fall back to a default)."""

    def __init__(self, answers: List[str], fallback: str = "1"):
        self.answers = list(answers)
        self.fallback = fallback
        self.i = 0

    def choose(self, observation, label, menu, faction):
        if self.i < len(self.answers):
            ans = self.answers[self.i]
            self.i += 1
            return ans
        choices = _valid_choices(menu)
        return choices[0] if choices else self.fallback


class FirstChoicePolicy(Policy):
    """Always take the first legal option (and the minimum count)."""

    def choose(self, observation, label, menu, faction):
        choices = _valid_choices(menu)
        return choices[0] if choices else ""


_SYSTEM_PROMPT = """\
You are an expert player of the COIN board game *Liberty or Death: The American \
Insurrection* (GMT Games).  You control the {faction} faction in a game where \
the other factions are played by rule-based bots.

You will be shown the current board state and a menu of LEGAL choices (every \
option offered is already a legal move).  Choose the single option that best \
advances {faction}'s victory conditions, thinking a few moves ahead about \
control, support/opposition, casualties, and the sequence of play.

Respond with ONLY the number of your chosen option (for a count prompt, respond \
with the number you want).  No explanation, just the number."""


class AnthropicPolicy(Policy):
    """Query an Anthropic model for each decision.

    Requires the ``anthropic`` package and an API key (``ANTHROPIC_API_KEY`` by
    default).  The response is parsed to a single number and clamped to a legal
    choice, with a safe fallback if parsing fails.
    """

    def __init__(self, model: str = "claude-sonnet-4-5", api_key: Optional[str] = None,
                 max_tokens: int = 16, temperature: float = 0.2,
                 verbose: bool = False):
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "AnthropicPolicy needs the 'anthropic' package: pip install anthropic"
            ) from exc
        self._client = anthropic.Anthropic(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY")
        )
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.verbose = verbose

    def _fallback(self, menu):
        choices = _valid_choices(menu)
        return choices[0] if choices else ""

    def choose(self, observation, label, menu, faction):
        valid = _valid_choices(menu)
        user = observation + "\n\nDECISION: " + (menu or {}).get("prompt", label) + "\n"
        if menu and menu.get("kind") == "select":
            for i, opt in enumerate(menu.get("options", []), 1):
                user += f"  {i}. {opt}\n"
            if menu.get("allow_back"):
                user += f"  0. {menu.get('back_label', 'Back/Done')}\n"
            user += "Reply with the option number."
        elif menu and menu.get("kind") == "count":
            user += f"Reply with an integer from {menu.get('min')} to {menu.get('max')}."
        else:
            user += "Reply with your choice."

        try:
            msg = self._client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=_SYSTEM_PROMPT.format(faction=faction or "your"),
                messages=[{"role": "user", "content": user}],
            )
            text = "".join(
                b.text for b in msg.content if getattr(b, "type", "") == "text"
            )
        except Exception as exc:  # pragma: no cover
            if self.verbose:
                print(f"[AnthropicPolicy] API error: {exc}; using fallback")
            return self._fallback(menu)

        m = re.search(r"-?\d+", text)
        if not m:
            return self._fallback(menu)
        ans = m.group(0)
        if valid and ans not in valid:
            if menu and menu.get("kind") == "count":
                return str(max(menu["min"], min(menu["max"], int(ans))))
            return self._fallback(menu)
        if self.verbose:
            print(f"[AnthropicPolicy] {faction} -> {ans}")
        return ans


def make_policy(name: str, **kwargs) -> Policy:
    """Factory: 'random', 'first', or 'anthropic'."""
    name = (name or "random").lower()
    if name == "random":
        return RandomPolicy(seed=kwargs.get("seed", 0))
    if name == "first":
        return FirstChoicePolicy()
    if name in ("anthropic", "claude", "llm"):
        return AnthropicPolicy(model=kwargs.get("model", "claude-sonnet-4-5"),
                               verbose=kwargs.get("verbose", False))
    raise ValueError(f"Unknown policy: {name!r}")
