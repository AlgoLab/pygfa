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

    def overlap_consistency(self, external_fasta_file=None):
        """Check overlap consistency between CIGAR overlaps and actual sequence overlaps.
        
        This method compares the CIGAR overlap specified in edges with the actual
        sequence overlap computed from the node sequences. If an external FASTA file
        is provided, it will be used to resolve sequences that are not stored in the
        graph (marked as "*").
        
        :param external_fasta_file: Optional path to a FASTA file containing node
            sequences. The path should be relative to the data directory.
        :return: A tuple of (edges_no_consistency, edges_no_calculate) where:
            - edges_no_consistency: List of edge IDs where CIGAR and sequence overlaps
              don't match
            - edges_no_calculate: List of edge IDs where overlap couldn't be calculated
              (e.g., missing sequence data)
        :return: None if the external FASTA file is specified but not found
        """
        from pygfa.graph_operations.overlap_consistency import check_overlap
        import os
        
        # Determine the path to the data directory
        if external_fasta_file:
            dir_path = os.path.dirname(external_fasta_file)
            if dir_path and not dir_path.endswith(os.sep):
                dir_path += os.sep
            filename = os.path.basename(external_fasta_file)
            return check_overlap(self, dir_path, filename)
        else:
            return check_overlap(self, "", None)


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
