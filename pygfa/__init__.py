from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pygfa.gfa import GFA

from pygfa import bgfa, gfa
from pygfa.bgfa import to_bgfa  # noqa: F401
from pygfa.operations import nodes_connected_component, nodes_connected_components  # noqa: F401

__version__ = "0.1.0"
__all__ = [
    "GFA",
    "bgfa",
    "gfa",
    "nodes_connected_component",
    "nodes_connected_componentsto_bgfa",
]
