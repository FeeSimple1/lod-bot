"""
shim: keep old imports working

    from lod_ai.util.adjacency import is_adjacent

while the real function now lives in lod_ai.map.adjacency.
"""

from lod_ai.map.adjacency import is_adjacent  # re-export