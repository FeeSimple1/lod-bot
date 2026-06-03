"""LLM harness: let a language model play Liberty or Death as a human faction
against the rule-based bots, by answering the existing CLI wizards.

Quick start:

    from lod_ai.llm import run_game
    from lod_ai.llm.policy import RandomPolicy, AnthropicPolicy

    # Offline smoke test (no API):
    result = run_game("1778", seed=1, llm_factions=["PATRIOTS"], policy=RandomPolicy())

    # Real LLM play (needs ANTHROPIC_API_KEY):
    result = run_game("1775", llm_factions=["PATRIOTS"], policy=AnthropicPolicy())
"""
from .harness import run_game
from .policy import (
    Policy, RandomPolicy, ScriptedPolicy, FirstChoicePolicy,
    AnthropicPolicy, make_policy,
)
from .observation import serialize_state

__all__ = [
    "run_game", "serialize_state",
    "Policy", "RandomPolicy", "ScriptedPolicy", "FirstChoicePolicy",
    "AnthropicPolicy", "make_policy",
]
