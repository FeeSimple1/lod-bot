# lod_ai/engine.py
# ============================================================
# Minimal driver to:
#   • pop & execute queued free Ops
#   • select a regular Command via bot logic or CLI
#   • run Winter-Quarters upkeep
#   • refresh Control and caps after every action
# ============================================================

from lod_ai.dispatcher    import Dispatcher
from lod_ai.util.free_ops import pop_free_ops
from lod_ai.cards import determine_eligible_factions
from lod_ai.util.year_end import resolve as resolve_year_end
from lod_ai.util.history  import push_history
from lod_ai import rules_consts as C
from lod_ai.util.normalize_state import normalize_state
from lod_ai.util import eligibility as elig

# Command / SA implementations
from lod_ai.commands import march, rally, battle, gather, muster, scout, raid
from lod_ai.special_activities import skirmish, war_path, partisans, common_cause, trade
from lod_ai.bots.british_bot import BritishBot
from lod_ai.bots.patriot import PatriotBot
from lod_ai.bots.french import FrenchBot
from lod_ai.bots.indians import IndianBot

# ---------------------------------------------------------------------------
class Engine:
    def __init__(self, initial_state: dict, use_cli: bool = False):
        self.state       = initial_state
        normalize_state(self.state)
        self.ctx: dict   = {}          # scratch context per action
        self.dispatcher  = Dispatcher()
        self.use_cli     = use_cli

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
    def _start_card(self, card: dict) -> tuple[str | None, str | None]:
        """Prepare eligibility and return acting factions for *card*."""
        elig_map = self.state.setdefault("eligible", {})
        for fac in self.state.pop("eligible_next", set()):
            elig_map[fac] = True
        for fac in self.state.pop("ineligible_next", set()):
            elig_map[fac] = False
        for fac in elig.consume_ineligible_through_next(self.state):
            elig_map[fac] = False
        order = determine_eligible_factions(self.state, card)
        self.state["current_card"] = card
        self.state["card_order"] = order
        return order

    def play_card(self, card: dict) -> None:
        """Execute all eligible turns for *card*."""
        first, second = self._start_card(card)
        for fac in (first, second):
            if fac and self.state.get("eligible", {}).get(fac, True):
                self.play_turn(fac, card=card)
    # -------------------------------------------------------------------

    def _cli_select_command(self, faction: str) -> None:
        """Simple interactive prompt to choose a Command and location."""
        cmds = sorted(self.dispatcher._cmd.keys())
        print(f"Manual turn for {faction}. Available commands:")
        for idx, lbl in enumerate(cmds, 1):
            print(f"  {idx}. {lbl}")
        choice = input("Select command by number or name: ").strip()
        if choice.isdigit():
            idx = int(choice) - 1
            cmd = cmds[idx] if 0 <= idx < len(cmds) else None
        else:
            cmd = choice
        if not cmd:
            print("Invalid command; skipping turn")
            return
        loc = input("Space id (blank for none): ").strip() or None
        self.dispatcher.execute(cmd.lower(), faction=faction, space=loc)
        push_history(self.state, f"{faction} manually executes {cmd}")
    # -------------------------------------------------------------------

    def play_turn(self, faction: str, card: dict | None = None) -> None:
        """
        Execute one full turn for *faction*.

        Steps:
            1. Resolve Winter-Quarters upkeep if flagged.
            2. Execute any queued free Command or SA and end the turn.
            3. Otherwise run a normal Command chosen by a bot or via CLI.
        """
        # 0) Winter-Quarters upkeep (noop if no flag)
        resolve_year_end(self.state)

        # 1) Consume queued free Ops
        ops = pop_free_ops(self.state, faction)
        if ops:
            for _fac, _op, _loc in ops:  # execute all queued ops FIFO
                self.dispatcher.execute(_op, faction=_fac, space=_loc, free=True)
                push_history(self.state, f"FREE {_op.upper()} by {_fac} in {_loc or 'chosen space'}")
                normalize_state(self.state)
            return  # free ops consume the turn

        # 2) Normal Command via bot or CLI
        faction = faction.upper()
        bot = self.bots.get(faction)
        card = card or self.state.get("upcoming_card", {})

        if bot is not None and not self.use_cli:
            bot.take_turn(self.state, card)
        else:
            self._cli_select_command(faction)

        normalize_state(self.state)

        # mark faction ineligible for remainder of card and queue for next card
        if faction in self.state.get("remain_eligible", set()):
            elig.clear_remain_eligible(self.state, faction)
        else:
            elig_map = self.state.setdefault("eligible", {})
            elig_map[faction] = False
            self.state.setdefault("eligible_next", set()).discard(faction)
            self.state.setdefault("ineligible_next", set()).add(faction)
