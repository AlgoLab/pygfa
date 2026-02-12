"""
Base GFA class with core data structures and basic operations.

This module provides the foundation for the GFA (Graphical Fragment Assembly)
graph representation using networkx MultiGraph.
"""

from __future__ import annotations

import copy
import logging
import re
from typing import Any

import networkx as nx

from pygfa.exceptions import InvalidElementError, InvalidSearchParameters
from pygfa.graph_element import edge as ge
from pygfa.graph_element import node
from pygfa.graph_element import subgraph as sg

GRAPH_LOGGER = logging.getLogger(__name__)


class Element:
    """Represent the types of graph a GFA graph object can have."""

    NODE = 0
    EDGE = 1
    SUBGRAPH = 2
    PATH = 3
    WALK = 4


def _index(obj: Any, other: list[Any]) -> tuple[bool, int]:
    """Given an object O and a list
    of objects L check that exist an object O'
    in the list such that O == O'.

    :return True: If O' exists.
    :return: The position of O' in the list.
    """
    found = False
    index = 0
    max_len = len(other)
    while not found and index < max_len:
        if obj == other[index]:
            found = True
        else:
            index += 1
    return found, index


class BaseGFA:
    """Base GFA class with core data structures.

    GFA will use a networkx MultiGraph as structure to contain
    the elements of the specification.
    GFA graphs directly accept only instances coming from the
    graph_elements package, but can contains any kind of data
    undirectly by accessing the `_graph` attribute.
    """

    def __init__(self, base_graph: nx.MultiGraph | None = None) -> None:
        """Creates a GFA graph.

        If :param base_graph: is not `None` use the graph provided
        as base for the graph.

        A `virtual id` is assigned to edges(graph edges) that don't
        have an id.
        Their id will be `virtual_#` where `#` will be given
        by `next_virtual_id`.

        :param base_graph: An instance of a networkx.MultiGraph.
        :raises TypeError: If base_graph is not a MultiGraph.
        """
        if base_graph is not None and not isinstance(base_graph, nx.MultiGraph):
            raise InvalidElementError(
                f"{type(base_graph)} cannot be used as base graph, use networkx.MultiGraph instead."
            )

        self._graph = nx.MultiGraph(base_graph)
        self._subgraphs: dict[str, Any] = {}
        self._segment_map: dict[str, int] = {}
        self._paths: dict[str, Any] = {}
        self._walks: dict[str, Any] = {}
        self._header_info: dict[str, Any] = {}
        self._next_virtual_id: int = 0 if base_graph is None else self._find_max_virtual_id()

        # Initialize segment map from base_graph if provided
        if base_graph is not None and hasattr(base_graph, "_segment_map"):
            self._segment_map = base_graph._segment_map.copy()
        if base_graph is not None and hasattr(base_graph, "_header_info"):
            self._header_info = base_graph._header_info.copy()

    def __contains__(self, id_: str) -> bool:
        """Check if an element with the given id exists in the graph.

        :param id_: The identifier to check.
        :returns: True if the element exists.
        """
        try:
            if self._graph.has_node(id_):
                return True
            edge_keys = (
                key
                for from_node in self._graph.adj
                for to_node in self._graph.adj[from_node]
                for key in self._graph.adj[from_node][to_node]
            )
            if id_ in edge_keys:
                return True
            if id_ in self._subgraphs:
                return True
            if id_ in self._paths:
                return True
            if id_ in self._walks:
                return True
            return False
        except TypeError:
            return False

    def __iter__(self):
        """Iterate over all elements in the graph."""
        # Yield nodes
        for node_id in self._graph.nodes():
            yield node_id
        # Yield edges
        for edge_key in self._edge_keys():
            yield edge_key
        # Yield subgraphs
        for subgraph_id in self._subgraphs:
            yield subgraph_id
        # Yield paths
        for path_id in self._paths:
            yield path_id
        # Yield walks
        for walk_id in self._walks:
            yield walk_id

    def __len__(self) -> int:
        """Return the total number of elements in the graph."""
        return (
            self._graph.number_of_nodes()
            + self._graph.number_of_edges()
            + len(self._subgraphs)
            + len(self._paths)
            + len(self._walks)
        )

    def _edge_keys(self):
        """Generator to yield all edge keys."""
        for from_node in self._graph.adj:
            for to_node in self._graph.adj[from_node]:
                for key in self._graph.adj[from_node][to_node]:
                    yield key

    def clear(self) -> None:
        """Clear all GFA object elements.

        Call networkx `clear` method, reset the virtual id counter and
        delete all the subgraphs, paths, and walks.
        """
        self._graph.clear()
        self._next_virtual_id = 0
        self._subgraphs.clear()
        self._paths.clear()
        self._walks.clear()
        self._segment_map.clear()
        self._header_info.clear()

    def _get_virtual_id(self, increment: bool = True) -> int:
        """Return the next virtual id value available.

        :param increment: If set to False, the virtual id is not
            incremented. Useful mainly in interactive mode.
        :returns: The next virtual id.
        """
        key = self._next_virtual_id
        if increment:
            self._next_virtual_id += 1
        return key

    def _find_max_virtual_id(self) -> int:
        """Traverse the graph to find the greatest virtual id value."""
        # nodes cannot have a virtual_id, so don't search inside them
        virtual_rxp = r"^virtual_(\d+)$"
        regexp = re.compile(virtual_rxp)
        virtual_keys = [0]

        for _from_node, _to_node, key in self.edges_iter(keys=True):
            match = regexp.fullmatch(key)
            if match:
                virtual_keys.append(int(match.group(1)))

        for key in self._subgraphs.keys():
            match = regexp.fullmatch(key)
            if match:
                virtual_keys.append(int(match.group(1)))

        for key in self._paths.keys():
            match = regexp.fullmatch(key)
            if match:
                virtual_keys.append(int(match.group(1)))

        for key in self._walks.keys():
            match = regexp.fullmatch(key)
            if match:
                virtual_keys.append(int(match.group(1)))

        return max(virtual_keys)

    def _search_edge_by_key(self, edge_key: str) -> dict[str, Any] | None:
        """Search for an edge by its key.

        :param edge_key: The edge key to search for.
        :returns: The edge data if found, None otherwise.
        """
        from_node, to_node = self._get_edge_end_nodes(edge_key)
        if (from_node, to_node) != (None, None):
            return self._graph.get_edge_data(from_node, to_node, edge_key)
        return None

    def _search_edge_by_nodes(self, nodes: tuple) -> dict[str, Any] | None:
        """Search for edge and edges providing end nodes.

        If given a tuple with from_node and to_node return all the edges
        between the two nodes.

        If a third element is present in the tuple return the exact edge
        between the two nodes with the key specified by the third element.
        If no match is found return `None`.

        :param nodes: A tuple of (from_node, to_node) or (from_node, to_node, key).
        :returns: Edge data or list of edge data.
        :raises InvalidSearchParameters: If less than 2 nodes provided.
        """
        if len(nodes) < 2:
            raise InvalidSearchParameters("At least two values are required.")
        from_node = nodes[0]
        to_node = nodes[1]
        try:
            if len(nodes) > 2:
                key = nodes[2]
                return self._graph.get_edge_data(from_node, to_node, key)
            return self._graph.get_edge_data(from_node, to_node)
        except Exception:
            return None

    def _get_edge_end_nodes(self, edge_key: str) -> tuple[str | None, str | None]:
        """Given an edge key return a tuple that contains
        the end nodes for that edge.

        :param edge_key: The edge key to look up.
        :returns: Tuple of (from_node, to_node) or (None, None) if not found.
        """
        for from_node, to_node, key in self.edges_iter(keys=True):
            if key == edge_key:
                return from_node, to_node
        return None, None

    def get(self, key: str) -> Any | None:
        """Return the element pointed by the specified key.

        :param key: The identifier to look up.
        :returns: The element if found, None otherwise.
        """
        if self._graph.has_node(key):
            return self.nodes(data=True, identifier=key)
        if key in self._subgraphs:
            return self._subgraphs[key]
        if key in self._paths:
            return self._paths[key]
        if key in self._walks:
            return self._walks[key]
        edge_ = self._search_edge_by_key(key)
        if edge_ is not None:
            return edge_
        return None

    def as_graph_element(self, key: str) -> Any:
        """Given a key of an existing node, edge or subgraph, return
        its equivalent graph element object.

        :param key: The identifier to look up.
        :returns: The graph element object.
        :raises InvalidElementError: If the key doesn't exist.
        """
        element = self.get(key)
        if element is None:
            raise InvalidElementError(f"No graph element has the given key: {key}")

        # Subgraph objects don't need to be converted
        if sg.is_subgraph(element):
            return copy.deepcopy(element)

        # Path objects don't need to be converted
        if isinstance(element, dict) and "path_name" in element:
            return copy.deepcopy(element)

        # Walk objects don't need to be converted
        if isinstance(element, dict) and "sample_id" in element:
            return copy.deepcopy(element)

        tmp_list = copy.deepcopy(element)
        try:
            if "nid" in element:
                tmp_list.pop("nid")
                tmp_list.pop("sequence")
                tmp_list.pop("slen")
                return node.Node(
                    element["nid"],
                    element["sequence"],
                    element["slen"],
                    opt_fields=tmp_list,
                )
            if "eid" in element:
                tmp_list.pop("eid")
                tmp_list.pop("from_node")
                tmp_list.pop("from_orn")
                tmp_list.pop("to_node")
                tmp_list.pop("to_orn")
                tmp_list.pop("from_positions")
                tmp_list.pop("to_positions")
                tmp_list.pop("alignment")
                tmp_list.pop("variance")
                tmp_list.pop("distance")
                edge_ = ge.Edge(
                    element["eid"],
                    element["from_node"],
                    element["from_orn"],
                    element["to_node"],
                    element["to_orn"],
                    element["from_positions"],
                    element["to_positions"],
                    element["alignment"],
                    element["distance"],
                    element["variance"],
                    opt_fields=tmp_list,
                )
                return edge_
        except KeyError:
            return None
        return None

    def edges_iter(self, **kwargs):
        """Return an iterator over the edges in the graph.

        Interface to the networkx method.

        :param kwargs: Additional arguments passed to networkx.edges().
        :returns: Iterator over edges.
        """
        return iter(self._graph.edges(**kwargs))

    def nodes_iter(self, data: bool = False, with_sequence: bool = False):
        """Return an iterator over nodes in the graph.

        :param data: If True, return node data as well.
        :param with_sequence: If set return only nodes with
            a sequence property.
        :returns: Iterator over nodes.
        """
        if with_sequence is True:
            if data is True:
                return iter((nid, data_) for nid, data_ in self._graph.nodes(data=True) if "sequence" in data_)
            else:
                return iter(nid for nid, data_ in self._graph.nodes(data=True) if "sequence" in data_)
        else:
            return iter(list(self._graph.nodes(data=data)))

    def subgraphs_iter(self, data: bool = False):
        """Return an iterator over the subgraphs in the graph.

        :param data: If True, return subgraph objects.
        :returns: Iterator over subgraphs.
        """
        if data is True:
            return iter(self._subgraphs.items())
        return iter(self._subgraphs.keys())

    def paths_iter(self, data: bool = False):
        """Return an iterator over the paths in the graph.

        :param data: If True, return path objects.
        :returns: Iterator over paths.
        """
        if data is True:
            return iter(self._paths.items())
        return iter(self._paths.keys())

    def walks_iter(self, data: bool = False):
        """Return an iterator over the walks in the graph.

        :param data: If True, return walk objects.
        :returns: Iterator over walks.
        """
        if data is True:
            return iter(self._walks.items())
        return iter(self._walks.keys())

    def nbunch_iter(self, nbunch=None):
        """Return an iterator of nodes contained in nbunch that are
        also in the graph.

        Interface to the networkx method.
        """
        return self._graph.nbunch_iter(nbunch=nbunch)
