from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pygfa.gfa import GFA

from pygfa import bgfa, gfa
from pygfa.bgfa import to_bgfa
from pygfa.dovetail_operations.operations import *  # noqa: F403
from pygfa.operations import *
from pygfa.dovetail_operations.simple_paths import dovetails_all_simple_paths
from pygfa.dovetail_operations.linear_paths import dovetails_linear_paths

__version__ = "0.1.0"
__all__ = [
    "GFA",
    "bgfa",
    "gfa",
    "nodes_connected_component",  # noqa: F405
    "nodes_connected_components",  # noqa: F405
    "to_bgfa",
    "dovetails_remove_small_components",  # noqa: F405
    "dovetails_remove_dead_ends",  # noqa: F405
    "dovetails_all_simple_paths",  # noqa: F405
    "dovetails_linear_paths",  # noqa: F405
    "dovetails_articulation_points",  # noqa: F405
]
