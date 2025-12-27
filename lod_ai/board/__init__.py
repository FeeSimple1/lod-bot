"""
lod_ai.board

Re-export board helpers without creating circular imports.
The canonical implementation of refresh_control lives in lod_ai.board.control.
"""

from .control import refresh_control

__all__ = ["refresh_control"]
