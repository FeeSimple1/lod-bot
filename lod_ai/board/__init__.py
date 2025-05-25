# lod_ai/board/__init__.py
"""
Shim module: re-export mutable board helpers.

This keeps older imports like
    from lod_ai.board.control import refresh_control
working, while the actual implementation now lives in
lod_ai.map.control.refresh_control.
"""

from lod_ai.map.control import refresh_control  # re-export
