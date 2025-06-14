"""
lod_ai.util.loss_mod
====================

Central place to enqueue and consume temporary Battle loss modifiers.
Each entry is a tuple (space, att_delta, def_delta).  The Battle routine
will pop the first matching entry (FIFO) before resolving losses.
"""

from typing import Dict, Any
from lod_ai.util.history import push_history

def queue_loss_mod(state: Dict[str, Any],
                   space: str | None,
                   att_delta: int = 0,
                   def_delta: int = 0) -> None:
    """
    Enqueue a modifier that applies to the *next* Battle.
      space=None  → any Battle will consume it.
    """
    state.setdefault("loss_mod_queue", []).append((space, att_delta, def_delta))
    push_history(state, f"Queued loss mod {att_delta}/{def_delta} for {space or 'any space'}")

def pop_loss_mod(state: Dict[str, Any], space: str) -> tuple[int, int]:
    """
    Called by the Battle routine.  Removes the first entry that matches
    'space' or has space==None.  Returns (att_delta, def_delta) or (0,0).
    """
    q = state.get("loss_mod_queue", [])
    for idx, (sp, att, defe) in enumerate(q):
        if sp is None or sp == space:
            q.pop(idx)
            return att, defe
    return 0, 0
