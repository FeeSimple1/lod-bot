"""
Compatibility shim.

`refresh_control` is canonically implemented in lod_ai.board.control.
Importing it from here remains supported for older call sites.
"""

from lod_ai.board.control import refresh_control

__all__ = ["refresh_control"]
