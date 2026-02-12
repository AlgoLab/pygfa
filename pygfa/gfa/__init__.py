"""
GFA (Graphical Fragment Assembly) graph representation.

This package provides a modern, type-safe API for working with GFA files.
The main GFA class combines all functionality through multiple mixins:

- BaseGFA: Core data structures and basic operations
- GFAElementsMixin: Graph element operations (nodes, edges, paths, walks, subgraphs)
- GFAQueryMixin: Query and search operations
- GFAParserMixin: Parsing operations

Example usage:
    >>> from pygfa import GFA
    >>> g = GFA()
    >>> g.add_node(node.Node("s1", "ACGT", 4))
    >>> g.add_edge(edge.Edge(None, "s1", "+", "s2", "-", (0, 4), (0, 4), "4M", None, None))
    >>> g.to_gfa("output.gfa")
"""

from pygfa.gfa.base import BaseGFA, Element
from pygfa.gfa.elements import GFAElementsMixin
from pygfa.gfa.query import GFAQueryMixin, GFAParserMixin

__all__ = ["GFA", "Element", "BaseGFA"]


class GFA(GFAElementsMixin, GFAQueryMixin, GFAParserMixin):
    """Main GFA graph class.

    This class combines all functionality from the various mixins to provide
    a complete API for working with GFA graphs. It supports:

    - Node, edge, path, walk, and subgraph management
    - Querying and searching
    - I/O operations (GFA and BGFA formats)
    - Parsing from strings and files

    The graph is backed by a networkx MultiGraph for efficient storage and
    traversal of complex genome assembly graphs.

    Example:
        >>> g = GFA()
        >>> g.add_node(node.Node("s1", "ACGT", 4))
        >>> print(len(g))  # Total number of elements
        1
    """

    pass


# Re-export for convenience
from pygfa.graph_element import node, edge, subgraph

__all__.extend(["node", "edge", "subgraph"])

# Re-export exceptions for backward compatibility
from pygfa.exceptions import (
    GFAError,
    InvalidSearchParameters,
    InvalidElementError,
)

__all__.extend(["GFAError", "InvalidSearchParameters", "InvalidElementError"])
