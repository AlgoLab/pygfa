from typing import TYPE_CHECKING, Set, Iterator

from networkx.algorithms.components.connected import (
    node_connected_component as nx_node_connected_component,
)
from networkx.algorithms.components.connected import connected_components as nx_connected_components

import pygfa.gfa  # required for GFAError (gives error otherwise)

if TYPE_CHECKING:
    from pygfa.gfa import GFA


def nodes_connected_component(gfa_: "GFA", nid: str) -> Set[str]:
    """Return the connected component
    belonging to the given node.

    :param gfa_: The GFA object containing the graph.
    :param nid: The id of the node to find the reachable nodes.
    :return: A set of node IDs in the connected component.
    """
    if nid not in gfa_:
        raise pygfa.gfa.GFAError("The source node is not in the graph.")
    return nx_node_connected_component(gfa_._graph, nid)


def nodes_connected_components(gfa_: "GFA") -> Iterator[Set[str]]:
    """Return a generator of sets with nodes of each weakly
    connected component in the graph.

    :param gfa_: The GFA object containing the graph.
    :return: An iterator of sets, where each set contains node IDs.
    """
    return nx_connected_components(gfa_._graph)
