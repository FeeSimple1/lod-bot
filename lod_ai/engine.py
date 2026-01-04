# lod_ai/engine.py
# ============================================================
# Full Sequence-of-Play engine with eligibility, bot sandboxing,
# and legality enforcement for Commands, Specials, and Events.
# ============================================================

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import inspect
from typing import Any, Callable, Dict, Iterable, List, Tuple

from lod_ai.dispatcher import Dispatcher
from lod_ai.util.free_ops import pop_free_ops
from lod_ai.cards import CARD_HANDLERS, determine_eligible_factions, get_faction_order
from lod_ai.util.year_end import resolve as resolve_year_end
from lod_ai.util.history import push_history
from lod_ai import rules_consts as C
from lod_ai.util.normalize_state import normalize_state
from lod_ai.util import eligibility as elig
from lod_ai.state.setup_state import build_state
from lod_ai.economy import resources

# Command / SA implementations
from lod_ai.commands import march, rally, battle, gather, muster, scout, raid
from lod_ai.special_activities import skirmish, war_path, partisans, common_cause, trade
from lod_ai.bots.british_bot import BritishBot
from lod_ai.bots.patriot import PatriotBot
from lod_ai.bots.french import FrenchBot
from lod_ai.bots.indians import IndianBot


class Engine:
    def __init__(self, initial_state: dict | None = None, use_cli: bool = False):
        self.state = initial_state or build_state()
        normalize_state(self.state)
        self.ctx: dict = {}          # scratch context per action
        self.dispatcher = Dispatcher(self)
        self.use_cli = use_cli
        self.human_factions: set[str] = set()

        # ── core Command registrations ──────────────────────────────────
        self.dispatcher.register_cmd("march",  self._wrap_march())
        self.dispatcher.register_cmd("rally",  self._wrap_rally())
        # 'battle' is registered below as a wrapper that supports free/choices
        self.dispatcher.register_cmd("gather", self._wrap_gather())
        self.dispatcher.register_cmd("muster", self._wrap_muster())
        self.dispatcher.register_cmd("scout",  self._wrap_scout())
        self.dispatcher.register_cmd("raid",   self._wrap_raid())

        # ── wrappers used ONLY by the free-op queue ─────────────────────
        self.dispatcher.register_cmd(
            "skirmish",
            lambda faction, space_id=None, **k: skirmish.execute(
                self.state, faction, self.ctx,
                space_id=space_id,
                option=k.get("option", 1)
            )
        )

        self.dispatcher.register_cmd(
            "war_path",
            lambda faction, space_id=None, **k: war_path.execute(
                self.state, C.INDIANS, self.ctx,
                space_id=space_id,
                option=k.get("option", 1)
            )
        )

        # Normal Battle (used by free-ops and CLI)
        self.dispatcher.register_cmd(
            "battle",
            lambda faction, space_id=None, free=False, **k: battle.execute(
                self.state, faction, self.ctx,
                spaces=k.get("spaces") or ([space_id] if space_id else []),
                free=free
            )
        )

        # Battle with +2 Force Level (event wrapper)
        self.dispatcher.register_cmd(
            "battle_plus2",
            lambda faction, space_id=None, free=False, **k: battle.execute(
                self.state, faction, self.ctx,
                spaces=k.get("spaces") or ([space_id] if space_id else []),
                choices={"force_bonus": 2},
                free=free
            )
        )

        # Special-Activity wrappers
        self.dispatcher.register_sa(
            "partisans",
            lambda faction, space_id=None, **k: partisans.execute(
                self.state, faction, self.ctx, space_id=space_id, free=True
            )
        )
        self.dispatcher.register_sa(
            "common_cause",
            lambda faction, space_id=None, **k: common_cause.execute(
                self.state, faction, self.ctx, space_id=space_id, free=True
            )
        )
        self.dispatcher.register_sa(
            "trade",
            lambda faction, space_id=None, **k: trade.execute(
                self.state, faction, self.ctx, space_id=space_id, **k
            )
        )

        # --- bot instances ---------------------------------------------------
        self.bots = {
            C.BRITISH:  BritishBot(),
            C.PATRIOTS: PatriotBot(),
            C.FRENCH:   FrenchBot(),
            C.INDIANS:  IndianBot(),
        }

    # -------------------------------------------------------------------
    # Initialization helpers
    # -------------------------------------------------------------------
    def setup_scenario(self, year: str) -> None:
        """Set up board and deck for the given scenario year (e.g. '1775', '1776', '1778')."""
        self.state = build_state(year)
        normalize_state(self.state)
        self.ctx = {}

    def set_human_factions(self, factions) -> None:
        """Register which factions are controlled by humans."""
        self.human_factions = set(factions)
        self.dispatcher.set_human_factions(factions)

    def is_human_faction(self, faction: str) -> bool:
        """Return True if the given faction is human-controlled."""
        return faction in self.human_factions

    def add_resources(self, faction: str, amount: int) -> None:
        """Add resources to a faction (used when a faction passes)."""
        resources.add(self.state, faction, amount)

    # -------------------------------------------------------------------
    # Dispatcher adapters
    # -------------------------------------------------------------------
    def _wrap_march(self):
        def _runner(*, faction, space_id=None, free=False, **kwargs):
            sources = kwargs.get("sources") or ([space_id] if space_id else [])
            destinations = kwargs.get("destinations") or kwargs.get("dests") or []
            return march.execute(
                self.state, faction, self.ctx,
                sources, destinations,
                bring_escorts=kwargs.get("bring_escorts", False),
                limited=kwargs.get("limited", False),
                move_plan=kwargs.get("move_plan"),
            )
        return _runner

    def _wrap_rally(self):
        def _runner(*, faction, space_id=None, free=False, **kwargs):
            selected = kwargs.get("selected") or ([space_id] if space_id else [])
            return rally.execute(
                self.state, faction, self.ctx,
                selected,
                place_one=kwargs.get("place_one"),
                build_fort=kwargs.get("build_fort"),
                bulk_place=kwargs.get("bulk_place"),
                move_plan=kwargs.get("move_plan"),
                promote_space=kwargs.get("promote_space"),
                limited=kwargs.get("limited", False),
            )
        return _runner

    def _wrap_gather(self):
        def _runner(*, faction, space_id=None, free=False, **kwargs):
            selected = kwargs.get("selected") or ([space_id] if space_id else [])
            return gather.execute(
                self.state, faction, self.ctx,
                selected,
                place_one=kwargs.get("place_one"),
                build_village=kwargs.get("build_village"),
                bulk_place=kwargs.get("bulk_place"),
                move_plan=kwargs.get("move_plan"),
                limited=kwargs.get("limited", False),
            )
        return _runner

    def _wrap_muster(self):
        def _runner(*, faction, space_id=None, free=False, **kwargs):
            selected = kwargs.get("selected") or ([space_id] if space_id else [])
            return muster.execute(
                self.state, faction, self.ctx,
                selected,
                regular_plan=kwargs.get("regular_plan"),
                tory_plan=kwargs.get("tory_plan"),
                build_fort=kwargs.get("build_fort", False),
                reward_levels=kwargs.get("reward_levels", 0),
            )
        return _runner

    def _wrap_scout(self):
        def _runner(*, faction, space_id=None, free=False, **kwargs):
            src = kwargs.get("src") or space_id
            dst = kwargs.get("dst") or kwargs.get("dest")
            return scout.execute(
                self.state, faction, self.ctx,
                src, dst,
                n_warparties=kwargs.get("n_warparties", 0),
                n_regulars=kwargs.get("n_regulars", 0),
                n_tories=kwargs.get("n_tories", 0),
                skirmish=kwargs.get("skirmish", False),
            )
        return _runner

    def _wrap_raid(self):
        def _runner(*, faction, space_id=None, free=False, **kwargs):
            selected = kwargs.get("selected") or ([space_id] if space_id else [])
            return raid.execute(
                self.state, faction, self.ctx,
                selected,
                move_plan=kwargs.get("move_plan"),
            )
        return _runner

    # -------------------------------------------------------------------
    # State helpers
    # -------------------------------------------------------------------
    @contextmanager
    def _using_state(self, state: dict, ctx: dict) -> Iterable[None]:
        """Temporarily swap in a different state/ctx (for sandbox runs)."""
        old_state, old_ctx = self.state, self.ctx
        self.state, self.ctx = state, ctx
        try:
            yield
        finally:
            self.state, self.ctx = old_state, old_ctx

    def _reset_trace_on(self, target_state: dict) -> None:
        target_state["_turn_used_special"] = False
        target_state["_turn_affected_spaces"] = set()
        target_state.pop("_turn_command", None)
        target_state.pop("_turn_command_meta", None)

    def _execute_free_ops(self, target_state: dict, target_ctx: dict, faction: str) -> bool:
        """Execute and log any queued free ops for *faction*."""
        ops = pop_free_ops(target_state, faction)
        if not ops:
            return False

        with self._using_state(target_state, target_ctx):
            for _fac, _op, _loc in ops:  # execute all queued ops FIFO
                self.dispatcher.execute(_op, faction=_fac, space=_loc, free=True)
                push_history(target_state, f"FREE {_op.upper()} by {_fac} in {_loc or 'chosen space'}")
                normalize_state(target_state)
        return True

    def _base_order(self, card: dict) -> List[str]:
        if isinstance(card.get("order"), (list, tuple)) and card["order"]:
            base_order = [str(f).upper() for f in card["order"]]
        elif card.get("order_icons"):
            base_order = get_faction_order(card)
        else:
            first = (card.get("first") or card.get("first_faction"))
            second = (card.get("second") or card.get("second_faction"))
            base_order = [f for f in [first, second] if f]
            base_order = [str(f).upper() for f in base_order if f]
            for f in (C.BRITISH, C.PATRIOTS, C.INDIANS, C.FRENCH):
                if f not in base_order:
                    base_order.append(f)
        return base_order

    def _eligible_queue(self, card: dict) -> List[str]:
        elig_map = self.state.get("eligible", {})
        base_order = self._base_order(card)
        return [f for f in base_order if elig_map.get(f, True)]

    def _prepare_card(self, card: dict) -> List[str]:
        """Prepare eligibility and return the acting queue for *card*."""
        elig_map = self.state.setdefault("eligible", {})
        for fac in self.state.pop("eligible_next", set()):
            elig_map[fac] = True
        for fac in self.state.pop("ineligible_next", set()):
            elig_map[fac] = False
        for fac in elig.consume_ineligible_through_next(self.state):
            elig_map[fac] = False

        self.state["current_card"] = card
        self.state["card_order"] = determine_eligible_factions(self.state, card)
        self._reset_trace_on(self.state)
        return self._eligible_queue(card)

    def draw_card(self) -> dict | None:
        """Reveal the next card, updating current/upcoming/deck."""
        deck = list(self.state.get("deck", []))
        upcoming = self.state.pop("upcoming_card", None)

        if upcoming is not None:
            current = upcoming
        elif deck:
            current = deck.pop(0)
        else:
            return None

        next_upcoming = deck.pop(0) if deck else None

        if next_upcoming and next_upcoming.get("winter_quarters"):
            # Swap per Winter Quarters rule: WQ becomes current immediately
            self.state["current_card"] = next_upcoming
            self.state["upcoming_card"] = current if current else None
            self.state["deck"] = deck
            return next_upcoming

        self.state["deck"] = deck
        if next_upcoming:
            self.state["upcoming_card"] = next_upcoming
        self.state["current_card"] = current
        return current

    # -------------------------------------------------------------------
    # Legality helpers
    # -------------------------------------------------------------------
    def _options_for_slot(self, first_action: dict | None) -> Dict[str, Any]:
        """Return allowed actions and flags for the current slot."""
        if not first_action:
            return {
                "actions": {"pass", "event", "command"},
                "limited_only": False,
                "special_allowed": True,
                "event_allowed": True,
            }

        if first_action.get("action") == "event":
            return {
                "actions": {"pass", "command"},
                "limited_only": False,
                "special_allowed": True,
                "event_allowed": False,
            }

        if first_action.get("action") == "command":
            if first_action.get("used_special"):
                return {
                    "actions": {"pass", "command", "event"},
                    "limited_only": True,
                    "special_allowed": False,
                    "event_allowed": True,
                }
            return {
                "actions": {"pass", "command"},
                "limited_only": True,
                "special_allowed": False,
                "event_allowed": False,
            }

        return {
            "actions": {"pass", "event", "command"},
            "limited_only": False,
            "special_allowed": True,
            "event_allowed": True,
        }

    def _command_effect_count(self, state: dict) -> int:
        affected = state.get("_turn_affected_spaces", set())
        count = len(affected) if isinstance(affected, (set, list, tuple)) else 0
        if count == 0 and state.get("_turn_command") == "HORTELEZ":
            meta = state.get("_turn_command_meta", {})
            if meta.get("pay", 0) >= 1:
                count = 1
        return count

    def _is_action_legal(self, result: dict, allowed: Dict[str, Any], state: dict) -> bool:
        action = result.get("action")
        if action not in allowed.get("actions", set()):
            return False

        used_special = bool(state.get("_turn_used_special"))
        affected = self._command_effect_count(state)

        if action == "event":
            return allowed.get("event_allowed", False)

        if action == "command":
            if allowed.get("limited_only") and affected != 1:
                return False
            if allowed.get("limited_only") and used_special:
                return False
            if (not allowed.get("special_allowed", True)) and used_special:
                return False
            if affected < 1:
                return False
        return True

    def _ensure_result_dict(self, result: Any, state: dict, notes: str = "") -> dict:
        if not isinstance(result, dict):
            result = {"action": "command", "notes": notes}
        result.setdefault("used_special", bool(state.get("_turn_used_special")))
        return result

    def _simulate_action(
        self,
        faction: str,
        card: dict,
        allowed: Dict[str, Any],
        runner: Callable[[dict, dict], Any],
    ) -> Tuple[dict, bool, dict, dict]:
        sandbox_state = deepcopy(self.state)
        sandbox_ctx = deepcopy(self.ctx)
        self._reset_trace_on(sandbox_state)

        with self._using_state(sandbox_state, sandbox_ctx):
            if self._execute_free_ops(sandbox_state, sandbox_ctx, faction):
                result = {"action": "command", "used_special": bool(sandbox_state.get("_turn_used_special")), "notes": "free_ops"}
            else:
                result = runner(sandbox_state, sandbox_ctx)
                result = self._ensure_result_dict(result, sandbox_state)

        legal = self._is_action_legal(result, allowed, sandbox_state)
        return result, legal, sandbox_state, sandbox_ctx

    def _commit_state(self, sandbox_state: dict, sandbox_ctx: dict) -> None:
        self.state.clear()
        self.state.update(sandbox_state)
        self.ctx = sandbox_ctx
        normalize_state(self.state)

    # Public wrappers for sandbox operations -------------------------
    def simulate_action(
        self,
        faction: str,
        card: dict,
        allowed: Dict[str, Any],
        runner: Callable[[dict, dict], Any],
    ) -> Tuple[dict, bool, dict, dict]:
        """Expose sandbox simulation (used by CLI)."""
        return self._simulate_action(faction, card, allowed, runner)

    def commit_simulated_state(self, sandbox_state: dict, sandbox_ctx: dict) -> None:
        """Commit a previously simulated state."""
        self._commit_state(sandbox_state, sandbox_ctx)

    # -------------------------------------------------------------------
    # Eligibility + sequencing helpers
    # -------------------------------------------------------------------
    def _award_pass(self, faction: str) -> None:
        gain = 2 if faction in (C.BRITISH, C.FRENCH) else 1
        resources.add(self.state, faction, gain)
        push_history(self.state, f"{faction} PASS (+{gain} resources)")
        self.state.setdefault("eligible_next", set()).add(faction)
        self.state.setdefault("ineligible_next", set()).discard(faction)
        self.state.setdefault("eligible", {}).update({faction: False})

    def _mark_executed(self, faction: str) -> None:
        elig_map = self.state.setdefault("eligible", {})
        elig_map[faction] = False
        next_inel = self.state.setdefault("ineligible_next", set())
        next_el = self.state.setdefault("eligible_next", set())

        if faction in self.state.get("remain_eligible", set()):
            next_el.add(faction)
            next_inel.discard(faction)
            elig.clear_remain_eligible(self.state, faction)
        else:
            next_inel.add(faction)
            next_el.discard(faction)

    def handle_event(self, faction: str, card: dict, *, state: dict | None = None, shaded: bool | None = None) -> dict:
        """Execute the card event for *faction* on the provided state (defaults to engine state)."""
        target_state = state or self.state
        handler = CARD_HANDLERS.get(card.get("id"))
        if not handler:
            raise KeyError(f"No handler registered for card {card.get('id')}")

        shaded_available = bool(card.get("dual") and card.get("shaded_event"))
        unshaded_available = bool(card.get("unshaded_event"))

        if card.get("dual"):
            if shaded is None:
                shaded = faction in {C.PATRIOTS, C.FRENCH}
            if shaded and not shaded_available:
                raise ValueError("Shaded side unavailable for this card.")
            if (not shaded) and not unshaded_available:
                raise ValueError("Unshaded side unavailable for this card.")
        else:
            shaded = False

        previous_active = target_state.get("active")
        target_state["active"] = faction
        try:
            handler(target_state, shaded=bool(shaded))
        finally:
            if previous_active is None:
                target_state.pop("active", None)
            else:
                target_state["active"] = previous_active
        return {
            "action": "event",
            "used_special": bool(target_state.get("_turn_used_special")),
            "event_side": "shaded" if shaded else "unshaded",
        }

    # -------------------------------------------------------------------
    # Single-faction helper (compatibility hook for tests/monkeypatching)
    # -------------------------------------------------------------------
    def play_turn(
        self,
        faction: str,
        card: dict | None = None,
        *,
        allowed: Dict[str, Any] | None = None,
        human_decider: Callable[..., Tuple[dict, bool, dict, dict]] | None = None,
    ) -> dict | None:
        card = card or self.state.get("current_card", {})
        allowed = allowed or {
            "actions": {"pass", "event", "command"},
            "limited_only": False,
            "special_allowed": True,
            "event_allowed": True,
        }

        if faction in self.human_factions and human_decider:
            result, legal, sandbox_state, sandbox_ctx = human_decider(faction, card, allowed, self)
            if not legal:
                self._award_pass(faction)
                return {"action": "pass", "used_special": False}
            if sandbox_state is not None and sandbox_ctx is not None:
                self._commit_state(sandbox_state, sandbox_ctx)
        else:
            bot = self.bots.get(faction)
            if not bot:
                self._award_pass(faction)
                return {"action": "pass", "used_special": False}
            try:
                result, legal, sandbox_state, sandbox_ctx = self._simulate_action(
                    faction,
                    card,
                    allowed,
                    lambda s, _c: bot.take_turn(s, card),
                )
                if not legal:
                    self._award_pass(faction)
                    return {"action": "pass", "used_special": False}
                self._commit_state(sandbox_state, sandbox_ctx)
            except Exception:  # noqa: BLE001
                result = {"action": "command", "used_special": False}

        if result is None:
            result = {"action": "command", "used_special": bool(self.state.get("_turn_used_special"))}

        if result.get("action") == "pass":
            self._award_pass(faction)
        else:
            self._mark_executed(faction)
        return result

    # -------------------------------------------------------------------
    # Main card resolution
    # -------------------------------------------------------------------
    def play_card(self, card: dict, human_decider: Callable[..., Tuple[dict, bool, dict, dict]] | None = None) -> List[Tuple[str, dict]]:
        """Execute all eligible turns for *card* (bot- and human-aware)."""
        queue = self._prepare_card(card)
        actions: List[Tuple[str, dict]] = []
        first_action: dict | None = None

        while queue and len(actions) < 2:
            faction = queue.pop(0)
            allowed = self._options_for_slot(first_action)
            sig = inspect.signature(self.play_turn)
            if "allowed" in sig.parameters:
                result = self.play_turn(faction, card=card, allowed=allowed, human_decider=human_decider)
            else:
                result = self.play_turn(faction, card=card)
            if not result:
                result = {"action": "command", "used_special": bool(self.state.get("_turn_used_special"))}
            if result.get("action") == "pass":
                continue

            actions.append((faction, result))
            if first_action is None:
                first_action = result

        if card.get("winter_quarters"):
            resolve_year_end(self.state)

        return actions
