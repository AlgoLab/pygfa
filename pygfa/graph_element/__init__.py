"""Graph element module for pygfa.

Provides dataclasses for GFA graph elements: Node, Edge, Path, Walk, Subgraph.
"""

from pygfa.graph_element.node import Node, is_node, InvalidNodeError
from pygfa.graph_element.edge import Edge, is_edge, InvalidEdgeError
from pygfa.graph_element.path import Path, InvalidPathError
from pygfa.graph_element.walk import Walk, InvalidWalkError
from pygfa.graph_element import subgraph
from pygfa.graph_element import parser

__all__ = [
    # Classes
    "Node",
    "Edge",
    "Path",
    "Walk",
    # Functions
    "is_node",
    "is_edge",
    # Exceptions
    "InvalidNodeError",
    "InvalidEdgeError",
    "InvalidPathError",
    "InvalidWalkError",
    # Modules
    "subgraph",
    "parser",
]
