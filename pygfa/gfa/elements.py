"""
Graph element operations for GFA graphs.

This module provides methods for adding, removing, and accessing
nodes, edges, paths, walks, and subgraphs in a GFA graph.
"""

from __future__ import annotations

import copy
import logging
from typing import Any

import networkx as nx
from typing_extensions import Self

from pygfa.exceptions import GFAError
from pygfa.graph_element import edge as ge
from pygfa.graph_element import node
from pygfa.graph_element import subgraph as sg
from pygfa.graph_element.parser import containment, link, path, segment
from pygfa.gfa.base import BaseGFA

GRAPH_LOGGER = logging.getLogger(__name__)


class GFAElementsMixin(BaseGFA):
    """Mixin class providing graph element operations.

    This class provides methods for adding, removing, and accessing
    nodes, edges, paths, walks, and subgraphs in a GFA graph.
    """

    def add_graph_element(self, element: Any) -> None:
        """Add a graph element -Node, Edge or Subgraph- object to
        the graph.

        :param element: The graph element to add.
        """
        if isinstance(element, node.Node):
            self.add_node(element)
        elif isinstance(element, ge.Edge):
            self.add_edge(element)
        elif isinstance(element, sg.Subgraph):
            self.add_subgraph(element)
        elif isinstance(element, dict) and "path_name" in element:
            self.add_path(element)
        elif isinstance(element, dict) and "sample_id" in element:
            self.add_walk(element)

    # =========================================================================
    # Node Operations
    # =========================================================================

    def add_node(self, new_node: node.Node | str, safe: bool = False) -> bool:
        """Add a graph_element Node to the GFA graph
        using the node id as key.

        Its sequence and sequence length will be individual attributes
        on the graph and all the remainders optional field will be stored
        individually as node data.

        :param new_node: A graph_element.Node object or a string
            that can represent a node (such as the Segment line).
        :param safe: If set check if the given identifier has already
            been added to the graph, and in that case raise
            an exception.
        :returns: True if the node was added successfully.
        :raises InvalidNodeError: If the object is not a valid node.
        :raises GFAError: If safe=True and node already exists.
        """
        logger = logging.getLogger(__name__)
        logger.debug(f"add_node(): Adding node with ID: {new_node.nid if hasattr(new_node, 'nid') else 'unknown'}")

        if isinstance(new_node, str) and new_node[0] == "S":
            logger.debug("add_node(): Parsing node from string")
            new_node = node.Node.from_line(segment.SegmentV1.from_string(new_node.strip()))

        if not node.is_node(new_node):
            logger.debug("add_node(): Invalid node object")
            raise node.InvalidNodeError("The object given is not a node.")

        if safe and new_node.nid in self:
            logger.debug(f"add_node(): Node {new_node.nid} already exists (safe mode)")
            raise GFAError("An element with the same id already exists.")

        logger.debug(f"add_node(): Adding node {new_node.nid} to graph")
        self._graph.add_node(
            new_node.nid,
            nid=new_node.nid,
            sequence=new_node.sequence,
            slen=new_node.slen,
            **new_node.opt_fields,
        )
        logger.debug(f"add_node(): Node {new_node.nid} added successfully")
        return True

    def remove_node(self, nid: str) -> None:
        """Remove a node with nid as its node id.

        Edges containing nid as end node will be automatically
        deleted.

        :param nid: The id belonging to the node to delete.
        :raises InvalidNodeError: If `nid` doesn't point to any node.
        """
        try:
            self._graph.remove_node(nid)
        except Exception as err:
            raise node.InvalidNodeError(f"{nid} doesn't point to any node in the graph.") from err

    def nodes(self, data: bool = False, with_sequence: bool = False, identifier: str | None = None) -> Any:
        """Return a list of the nodes in the graph.

        :param data: If True, return node data as well.
        :param with_sequence: If set return only nodes with
            a `sequence` property.
        :param identifier: If provided, return only the node with this id.
        :returns: List of nodes or node data.
        """
        if identifier is not None:
            if self._graph.has_node(identifier):
                return self._graph.nodes(data=data)[identifier]
            else:
                return None

        if with_sequence is True:
            return list(self.nodes_iter(data=data, with_sequence=with_sequence))

        return self._graph.nodes(data=data)

    # =========================================================================
    # Edge Operations
    # =========================================================================

    def add_edge(self, new_edge: ge.Edge | str, safe: bool = False) -> None:
        """Add a graph_element Edge or a networkx edge to the GFA
        graph using the edge id as key.

        If its id is `*` or `None` the edge will be given a
        **virtual_id**, in either case the original edge id will
        be preserved as edge attribute.

        All edge attributes will be stored as networkx edge
        attributes and all the remainders optional field will be stored
        individually as edge data.

        :param new_edge: A graph_element.Edge object or a string
            that can represent an edge (such as the Link or Containment line).
        :param safe: If set, check if the edge already exists and if
            the nodes it connects exist.
        :raises InvalidEdgeError: If the object is not a valid edge.
        :raises GFAError: If safe=True and edge or nodes don't exist.
        """
        logger = logging.getLogger(__name__)
        logger.debug("add_edge(): Adding edge")

        if isinstance(new_edge, str):
            logger.debug(f"add_edge(): Parsing edge from string: {new_edge[:50]}...")
            if new_edge[0] == "L":
                new_edge = ge.Edge.from_line(link.Link.from_string(new_edge.strip()))
            elif new_edge[0] == "C":
                new_edge = ge.Edge.from_line(containment.Containment.from_string(new_edge.strip()))
            else:
                logger.debug("add_edge(): Invalid edge string")
                raise ge.InvalidEdgeError(
                    f"The string given doesn't represent a GFA line that could"
                    f" be represented as an edge,\n"
                    f"given: {new_edge}"
                )

        if not ge.is_edge(new_edge):
            logger.debug("add_edge(): Invalid edge object")
            raise ge.InvalidEdgeError("The object is not a valid edge.")

        key = new_edge.eid
        if new_edge.eid is None or new_edge.eid == "*":
            key = f"virtual_{self._get_virtual_id()}"
            logger.debug(f"add_edge(): Assigned virtual ID: {key}")

        if safe:
            logger.debug("add_edge(): Safe mode - checking existence")
            edge_exists = key in self
            node1_exists = new_edge.from_node in self
            node2_exists = new_edge.to_node in self
            if edge_exists:
                logger.debug(f"add_edge(): Edge {key} already exists")
                raise GFAError("An element with the same id already exists.")
            if not (node1_exists and node2_exists):
                logger.debug(f"add_edge(): Nodes not found: from={node1_exists}, to={node2_exists}")
                raise GFAError("From/To node are not already in the graph.")

        logger.debug(f"add_edge(): Adding edge {key} from {new_edge.from_node} to {new_edge.to_node}")
        self._graph.add_edge(
            new_edge.from_node,
            new_edge.to_node,
            key=key,
            eid=new_edge.eid,
            from_node=new_edge.from_node,
            from_orn=new_edge.from_orn,
            to_node=new_edge.to_node,
            to_orn=new_edge.to_orn,
            from_positions=new_edge.from_positions,
            to_positions=new_edge.to_positions,
            alignment=new_edge.alignment,
            distance=new_edge.distance,
            variance=new_edge.variance,
            from_segment_end=new_edge.from_orn,
            to_segment_end=new_edge.to_orn,
            **new_edge.opt_fields,
        )
        logger.debug(f"add_edge(): Edge {key} added successfully")

    def remove_edge(self, identifier: str | tuple) -> None:
        """Remove an edge or all edges identified by an id
        or by a tuple with end node, respectively.

        * If `identifier` is a two elements tuple remove all the
            all the edges between the two nodes.

        * If `identifier` is a three elements tuple remove the edge
            specified by the third element of the tuple with end nodes
            given by the first two elements of the tuple itself.

        * If `identifier` is not a tuple, treat it as it should be
            an edge id.

        :param identifier: Edge id or tuple of nodes.
        :raises InvalidEdgeError: If `identifier` is not valid.
        """
        try:
            if isinstance(identifier, tuple):
                if len(identifier) == 2:
                    self.remove_edges(identifier[0], identifier[1])
                else:
                    self._graph.remove_edge(identifier[0], identifier[1], identifier[2])
            else:
                from_node, to_node = self._get_edge_end_nodes(identifier)
                self._graph.remove_edge(from_node, to_node, identifier)
        except nx.NetworkXError as nxe:
            raise ge.InvalidEdgeError(nxe) from nxe

    def remove_edges(self, from_node: str, to_node: str) -> None:
        """Remove all the direct edges between the two nodes given.

        Call iteratively remove_edge (remove a not specified edge
        from `from_node` and `to_node`) for n-times where n is
        the number of edges between the given nodes,
        removing all the edges indeed.

        :param from_node: The source node id.
        :param to_node: The target node id.
        """
        num_edges = len(self.edges(identifier=(from_node, to_node)))
        for _ in range(0, num_edges):
            self._graph.remove_edge(from_node, to_node)

    def edges(self, identifier: str | tuple | None = None, adj_dict: bool = False, **kwargs) -> Any:
        """Return all the edges in the graph.

        :param identifier: If provided, return only the edge(s) with this id
            or between these nodes (if tuple).
        :param adj_dict: If True, return the adjacency dictionary.
        :param kwargs: Additional arguments passed to networkx.edges().
        :returns: List of edges or edge data.
        """
        if identifier is not None:
            if isinstance(identifier, tuple):
                return self._search_edge_by_nodes(identifier)
            else:
                return self._search_edge_by_key(identifier)

        if adj_dict is True:
            return self._graph.adj

        return self._graph.edges(**kwargs)

    # =========================================================================
    # Subgraph Operations
    # =========================================================================

    def add_subgraph(self, subgraph: sg.Subgraph, safe: bool = False) -> None:
        """Add a Subgraph object to the graph.

        The object is not altered in any way.

        :param subgraph: A graph_element.Subgraph object.
        :param safe: If set check if the given identifier has already
            been added to the graph, and in that case raise
            an exception.
        :raises InvalidSubgraphError: If the object is not a valid subgraph.
        :raises GFAError: If safe=True and subgraph already exists.
        """
        if not sg.is_subgraph(subgraph):
            raise sg.InvalidSubgraphError("The object is not a valid subgraph.")

        key = subgraph.sub_id
        if subgraph.sub_id is None or subgraph.sub_id == "*":
            key = f"virtual_{self._get_virtual_id()}"

        if safe and key in self:
            raise GFAError("An element with the same id already exists.")

        self._subgraphs[key] = copy.deepcopy(subgraph)

    def remove_subgraph(self, sub_id: str) -> None:
        """Remove a subgraph from the graph.

        :param sub_id: The id of the subgraph to remove.
        :raises GFAError: If the subgraph doesn't exist.
        """
        try:
            del self._subgraphs[sub_id]
        except KeyError as err:
            raise GFAError(f"The given id {sub_id} doesn't identify any subgraph.") from err

    def subgraphs(self, identifier: str | None = None) -> Any:
        """An interface to access to the subgraphs inside
        the GFA object.

        If `identifier` is `None` all the graph Subgraph objects are
        returned.

        :param identifier: The id of the subgraph to retrieve.
        :returns: Dict of subgraphs or a single subgraph.
        """
        if identifier is None:
            return self._subgraphs
        elif identifier in self._subgraphs:
            return self._subgraphs[identifier]
        return None

    # =========================================================================
    # Path Operations
    # =========================================================================

    def add_path(self, path_data: dict[str, Any] | str, safe: bool = False) -> None:
        """Add a path to the graph.

        The path_data should be a dictionary with:
        - 'path_name': the name of the path
        - 'segments': list of oriented segments (e.g., ['s1+', 's2-'])
        - 'overlaps': optional list of overlaps between segments
        - any optional fields

        :param path_data: Dictionary containing path information
        :param safe: If set, check if the path id already exists
        :raises GFAError: If the path data is invalid or already exists.
        """
        logger = logging.getLogger(__name__)
        logger.debug("add_path(): Adding path")

        if isinstance(path_data, str):
            logger.debug("add_path(): Parsing path from string")
            if path_data[0] == "P":
                # Parse the path line
                path_obj = path.Path.from_string(path_data.strip())
                # Convert to dictionary format
                path_data = {
                    "path_name": path_obj.fields["path_name"].value,
                    "segments": path_obj.fields["seqs_names"].value,
                    "overlaps": (path_obj.fields["overlaps"].value if "overlaps" in path_obj.fields else []),
                }
                # Add optional fields
                for field_name, field in path_obj.fields.items():
                    if field_name not in ["path_name", "seqs_names", "overlaps"]:
                        path_data[field_name] = field.value

        if not isinstance(path_data, dict) or "path_name" not in path_data:
            logger.debug("add_path(): Invalid path data format")
            raise GFAError("Invalid path data format.")

        key = path_data["path_name"]
        logger.debug(f"add_path(): Path name: {key}")
        if key == "*":
            key = f"virtual_{self._get_virtual_id()}"
            logger.debug(f"add_path(): Assigned virtual key: {key}")
        if safe and key in self._paths:
            logger.debug(f"add_path(): Path {key} already exists")
            raise GFAError("A path with the same id already exists.")

        # Store the path data
        logger.debug(f"add_path(): Storing path {key} with {len(path_data.get('segments', []))} segments")
        self._paths[key] = copy.deepcopy(path_data)
        logger.debug(f"add_path(): Path {key} added successfully")

    def remove_path(self, path_id: str) -> None:
        """Remove the path identified by the given id.

        :param path_id: The id of the path to remove.
        :raises GFAError: If the path doesn't exist.
        """
        try:
            del self._paths[path_id]
        except KeyError as err:
            raise GFAError("The given id doesn't identify any path.") from err

    def paths(self, identifier: str | None = None) -> Any:
        """An interface to access to the paths inside
        the GFA object.

        If `identifier` is `None` all the path objects are
        returned.

        :param identifier: The id of the path to retrieve.
        :returns: Dict of paths or a single path.
        """
        if identifier is None:
            return self._paths
        elif identifier in self._paths:
            return self._paths[identifier]
        return None

    # =========================================================================
    # Walk Operations
    # =========================================================================

    def add_walk(self, walk_data: dict[str, Any] | str, safe: bool = False) -> None:
        """Add a walk to the graph.

        The walk_data should be a dictionary with:
        - 'sample_id': the sample identifier
        - 'hapindex': the haplotype index
        - 'seq_id': the sequence identifier
        - 'seq_start': optional start position
        - 'seq_end': optional end position
        - 'walk': the walk string
        - any optional fields

        :param walk_data: Dictionary containing walk information
        :param safe: If set, check if the walk id already exists
        :raises GFAError: If the walk data is invalid or already exists.
        """
        logger = logging.getLogger(__name__)
        logger.debug("add_walk(): Adding walk")

        if isinstance(walk_data, str):
            logger.debug("add_walk(): Parsing walk from string")
            if walk_data[0] == "W":
                # Parse the walk line
                fields = walk_data.strip().split("\t")
                walk_data = {
                    "sample_id": fields[1],
                    "hapindex": int(fields[2]),
                    "seq_id": fields[3],
                    "seq_start": fields[4] if fields[4] != "*" else None,
                    "seq_end": fields[5] if fields[5] != "*" else None,
                    "walk": fields[6],
                }
                # Add optional fields
                for field in fields[7:]:
                    if ":" in field:
                        tag, type_, value = field.split(":", 2)
                        walk_data[tag] = value

        if not isinstance(walk_data, dict) or "sample_id" not in walk_data:
            logger.debug("add_walk(): Invalid walk data format")
            raise GFAError("Invalid walk data format.")

        # Create a unique key for the walk
        key = f"{walk_data['sample_id']}_{walk_data['hapindex']}_{walk_data['seq_id']}"
        logger.debug(f"add_walk(): Walk key: {key}")
        if safe and key in self._walks:
            logger.debug(f"add_walk(): Walk {key} already exists")
            raise GFAError("A walk with the same id already exists.")

        # Store the walk data
        logger.debug(f"add_walk(): Storing walk {key}")
        self._walks[key] = copy.deepcopy(walk_data)
        logger.debug(f"add_walk(): Walk {key} added successfully")

    def remove_walk(self, walk_id: str) -> None:
        """Remove the walk identified by the given id.

        :param walk_id: The id of the walk to remove.
        :raises GFAError: If the walk doesn't exist.
        """
        try:
            del self._walks[walk_id]
        except KeyError as err:
            raise GFAError("The given id doesn't identify any walk.") from err

    def walks(self, identifier: str | None = None) -> Any:
        """An interface to access to the walks inside
        the GFA object.

        If `identifier` is `None` all the walk objects are
        returned.

        :param identifier: The id of the walk to retrieve.
        :returns: Dict of walks or a single walk.
        """
        if identifier is None:
            return self._walks
        elif identifier in self._walks:
            return self._walks[identifier]
        return None
