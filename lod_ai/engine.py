# lod_ai/engine.py
# ============================================================
# Minimal driver to:
#   • pop & execute queued free Ops
#   • run Winter-Quarters upkeep
#   • refresh Control and caps after every action
# Normal bot/UI Command selection comes later.
# ============================================================

from lod_ai.dispatcher    import Dispatcher
from lod_ai.util.free_ops import pop_free_ops
from lod_ai.util.year_end import resolve as resolve_year_end
from lod_ai.util.history  import push_history
from lod_ai.util.caps     import enforce_global_caps
from lod_ai.board.control import refresh_control

# Command / SA implementations
from lod_ai.commands import march, rally, battle, gather, muster, scout, raid
from lod_ai.special_activities import skirmish, war_path, partisans, common_cause

# ---------------------------------------------------------------------------
class Engine:
    def __init__(self, initial_state: dict):
        self.state       = initial_state
        self.ctx: dict   = {}          # scratch context per action
        self.dispatcher  = Dispatcher()

        # ── core Command registrations ──────────────────────────────────
        self.dispatcher.register_cmd("march",  march.execute)
        self.dispatcher.register_cmd("rally",  rally.execute)
        self.dispatcher.register_cmd("battle", battle.execute)
        self.dispatcher.register_cmd("gather", gather.execute)
        self.dispatcher.register_cmd("muster", muster.execute)
        self.dispatcher.register_cmd("scout",  scout.execute)
        self.dispatcher.register_cmd("raid",   raid.execute)

        # ── wrappers used ONLY by the free-op queue ─────────────────────
        self.dispatcher.register_cmd(                      # free Skirmish
            "skirmish",
            lambda faction, space_id=None, **k: skirmish.execute(
                self.state, faction, self.ctx,
                space_id=space_id,
                option=k.get("option", 1)
            )
        )

        self.dispatcher.register_cmd(                      # free War-Path
            "war_path",
            lambda faction, space_id=None, **k: war_path.execute(
                self.state, "INDIANS", self.ctx,
                space_id=space_id,
                option=k.get("option", 1)
            )
        )

        self.dispatcher.register_cmd(                      # Battle +2 FL
            "battle_plus2",
            lambda faction, space_id=None, **k: battle.execute(
                self.state, faction, self.ctx,
                spaces=[space_id] if space_id else [],
                choices={"force_bonus": 2}
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
    # -------------------------------------------------------------------

    def play_turn(self, faction: str) -> None:
        """
        • Resolve Winter-Quarters if flagged.
        • If a free Command/SA is queued for *faction*, execute it and end turn.
        • (Normal Command/Event selection comes in a later milestone.)
        """
        # 0) Winter-Quarters upkeep (noop if no flag)
        resolve_year_end(self.state)

        # 1) Consume queued free Ops
        for _fac, _op, _loc in pop_free_ops(self.state, faction):
            self.dispatcher.execute(_op, faction=_fac, space=_loc, free=True)
            push_history(self.state, f"FREE {_op.upper()} by {_fac} in {_loc or 'chosen space'}")
            refresh_control(self.state)
            enforce_global_caps(self.state)
            return  # free action counts as the whole turn

        # 2) No free Op: bot/UI decision would go here
        raise NotImplementedError("Bot/UI selection not yet implemented")
