"""
shim: re-export refresh_control so
    from lod_ai.board.control import refresh_control
continues to work.
"""

from lod_ai.map.control import refresh_control   # re-export
