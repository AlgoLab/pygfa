"""
Query and search operations for GFA graphs.

This module provides methods for searching and querying
nodes, edges, and subgraphs in a GFA graph.
"""

from __future__ import annotations

import logging
from typing import Callable

from networkx import MultiGraph
from networkx.classes.function import all_neighbors as nx_all_neighbors

from pygfa.exceptions import GFAError
from pygfa.gfa.base import BaseGFA, Element
from pygfa.graph_element import subgraph as sg

GRAPH_LOGGER = logging.getLogger(__name__)


class GFAQueryMixin(BaseGFA):
    """Mixin class providing query and search operations.

    This class provides methods for searching and querying
    nodes, edges, and subgraphs in a GFA graph.
    """

    def neighbors(self, nid: str) -> list[str]:
        """Return all the nodes id of the nodes connected to
        the given node.

        Return all the predecessors and successors of the
        given source node.

        :param nid: The id of the selected node.
        :returns: List of neighbor node ids.
        :raises GFAError: If the node doesn't exist.
        """
        if self.nodes(identifier=nid) is None:
            raise GFAError("The source node is not in the graph.")
        return list(nx_all_neighbors(self._graph, nid))

    def search(self, comparator: Callable[[dict], bool], limit_type: int | None = None) -> list[str]:
        """Perform a query applying the comparator on each graph element.

        :param comparator: A function that takes a dictionary of element data
            and returns True if the element matches the search criteria.
        :param limit_type: If set, limit the search to only nodes, edges,
            or subgraphs. Use Element.NODE, Element.EDGE, or Element.SUBGRAPH.
        :returns: List of element ids that match the comparator.
        """
        if limit_type == Element.NODE:
            return self.search_on_nodes(comparator)
        elif limit_type == Element.EDGE:
            return self.search_on_edges(comparator)
        elif limit_type == Element.SUBGRAPH:
            return self.search_on_subgraph(comparator)

        retval: list[str] = []
        retval.extend(self.search_on_nodes(comparator))
        retval.extend(self.search_on_edges(comparator))
        retval.extend(self.search_on_subgraph(comparator))
        return retval

    def search_on_nodes(self, comparator: Callable[[dict], bool]) -> list[str]:
        """Search for nodes matching the comparator.

        :param comparator: A function that takes a dictionary of node data
            and returns True if the node matches the search criteria.
        :returns: List of node ids that match the comparator.
        """
        retval: list[str] = []
        for key, data in self.nodes_iter(data=True):
            try:
                if comparator(data):
                    retval.append(key)
            except KeyError:
                pass
        return retval

    def search_on_edges(self, comparator: Callable[[dict], bool]) -> list[str]:
        """Search for edges matching the comparator.

        :param comparator: A function that takes a dictionary of edge data
            and returns True if the edge matches the search criteria.
        :returns: List of edge ids (keys) that match the comparator.
        """
        retval: list[str] = []
        for _u, _v, key, data in self.edges_iter(data=True, keys=True):
            try:
                if comparator(data):
                    retval.append(key)
            except KeyError:
                pass
        return retval

    def search_on_subgraph(self, comparator: Callable[[dict], bool]) -> list[str]:
        """Search for subgraphs matching the comparator.

        :param comparator: A function that takes a dictionary of subgraph data
            and returns True if the subgraph matches the search criteria.
        :returns: List of subgraph ids that match the comparator.
        """
        retval: list[str] = []
        for key, data in self._subgraphs.items():
            data_dict = data.as_dict()
            try:
                if comparator(data_dict):
                    retval.append(key)
            except KeyError:
                pass
        return retval

    def get_subgraph(self, sub_key: str) -> "GFAQueryMixin":
        """Return a GFA subgraph from the parent graph.

        Return a new GFA graph structure with the nodes,
        edges and subgraphs specified in the elements attributes
        of the subgraph object pointed by the id.

        The returned GFA is *independent* from the original object.

        :param sub_key: The id of a subgraph present in the GFA graph.
        :returns: A new GFA graph containing the subgraph elements.
        :raises InvalidSubgraphError: If the subgraph id doesn't exist.
        """
        if sub_key not in self._subgraphs:
            raise sg.InvalidSubgraphError("There is no subgraph pointed by this key.")
        subgraph = self._subgraphs[sub_key]
        # Import here to avoid circular imports
        from pygfa.gfa import GFA

        sub_gfa = GFA()
        for id_ in subgraph.elements.keys():
            # creating a new GFA graph and the add method,
            # the virtual id are recomputed
            sub_gfa.add_graph_element(self.as_graph_element(id_))
        return sub_gfa

    def subgraph(self, nbunch: list[str], copy: bool = True) -> MultiGraph:
        """Given a bunch of nodes return a graph with
        all the given nodes and the edges between them.

        The returned object is not a GFA Graph, but a
        MultiGraph. To create a new GFA graph, just
        use the GFA initializer and give the subgraph to it.

        Interface to the networkx subgraph method.
        Given a collection of nodes return a subgraph with the nodes
        given and all the edges between each pair of nodes.

        :param nbunch: The nodes.
        :param copy: If set to True return a copy of the subgraph.
        :returns: A networkx MultiGraph subgraph.
        """
        subgraph_ = self._graph.subgraph(nbunch)
        if copy:
            return subgraph_.copy()
        return subgraph_
