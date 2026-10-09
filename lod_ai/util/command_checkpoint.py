"""Optional human Special Activity interruption points inside a Command.

The callback lives only in the current simulation context; command code stays
independent of the CLI and bots pay no input or timing overhead.
"""
from __future__ import annotations


def command_checkpoint(state: dict, ctx: dict, label: str,
                       space: str | None = None) -> None:
    callback = ctx.get("_command_checkpoint")
    if callable(callback):
        from lod_ai.util.caps import refresh_control
        refresh_control(state)
        callback(state, ctx, label, space)
