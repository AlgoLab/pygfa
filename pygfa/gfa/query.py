"""
Query and search operations for GFA graphs.

This module provides methods for searching and querying
nodes, edges, and subgraphs in a GFA graph.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Callable

import lark
import networkx as nx
from networkx.classes.function import all_neighbors as nx_all_neighbors

from pygfa.exceptions import GFAError, InvalidSearchParameters
from pygfa.gfa.base import BaseGFA, Element
from pygfa.graph_element import edge as ge
from pygfa.graph_element import node
from pygfa.graph_element import subgraph as sg
from pygfa.graph_element.parser import segment

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

    def subgraph(self, nbunch: list[str], copy: bool = True) -> nx.MultiGraph:
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


class GFAParserMixin(BaseGFA):
    """Mixin class providing parsing operations.

    This class provides methods for parsing GFA strings and files.
    """

    def from_string(self, string: str) -> None:
        """Add a GFA string to the graph once it has been
        converted.

        :param string: A string containing GFA format lines.
        """
        import logging

        logger = logging.getLogger(__name__)
        lines = re.split("\n", string)

        # Load the grammar from the gfa.lark file
        grammar_file = os.path.join(os.path.dirname(__file__), "..", "graph_element", "parser", "gfa.lark")
        with open(grammar_file) as f:
            grammar = f.read()

        # Create the parser
        parser = lark.Lark(grammar, start="start")
        logger.debug("Created parser for GFA parsing")

        for i, line_ in enumerate(lines):
            line_ = line_.strip()
            if len(line_) < 1:
                logger.debug(f"Skipping empty line {i + 1}")
                continue

            logger.debug(f"Processing line {i + 1}: {line_[:50]}{'...' if len(line_) > 50 else ''}")

            try:
                # Parse the line
                tree = parser.parse(line_ + "\n")
                logger.debug(f"Successfully parsed line {i + 1}")

                # Process the parsed tree based on line type
                for subtree in tree.children:
                    for child in subtree.children:
                        if child.data == "header_line":
                            # Handle header line
                            pass
                        elif child.data == "segment_line":
                            self._process_segment_line(child)
                        elif child.data == "link_line":
                            self._process_link_line(child, i, logger)
                        elif child.data == "containment_line":
                            # Handle containment line
                            pass
                        elif child.data == "path_line":
                            self._process_path_line(child)
                        elif child.data == "walk_line":
                            self._process_walk_line(child)
                        elif child.data == "jump_line":
                            logger.debug(f"Processing jump line at line {i + 1}")
                            pass

            except lark.exceptions.LarkError as e:
                # Skip lines that don't parse correctly
                logger.warning(f"Failed to parse line {i + 1}: {line_[:50]}{'...' if len(line_) > 50 else ''} - {e}")
                continue

        # Log graph dump
        logger.debug("Graph content after from_string():")
        for node_id, node_data in self.nodes_iter(data=True):
            logger.debug(
                f"  Node {node_id}: sequence={node_data.get('sequence', 'N/A')[:20]}..., "
                f"length={node_data.get('slen', 'N/A')}"
            )
        for u, v, key, data in self.edges_iter(data=True, keys=True):
            logger.debug(f"  Edge {key}: {u} -> {v}, alignment={data.get('alignment', 'N/A')}")
        for path_id, path_data in self.paths_iter(data=True):
            logger.debug(f"  Path {path_id}: segments={len(path_data.get('segments', []))}")
        for walk_id, walk_data in self.walks_iter(data=True):
            logger.debug(
                f"  Walk {walk_id}: sample={walk_data.get('sample_id', 'N/A')}, "
                f"walk_length={len(walk_data.get('walk', ''))}"
            )

    def _process_segment_line(self, child) -> None:
        """Process a parsed segment line and add it to the graph.

        :param child: The parsed segment line from lark.
        """
        segment_data: dict[str, Any] = {}
        for seg_child in child.children:
            if seg_child.data == "segment_name":
                segment_data["segment_name"] = seg_child.children[0].value
            elif seg_child.data == "seq_string":
                segment_data["sequence"] = seg_child.children[0].value
            elif seg_child.data == "optional_field":
                tag = seg_child.children[0].children[0].value
                _ = seg_child.children[1].children[0].value  # value_type
                value = seg_child.children[2].children[0].value
                segment_data[tag] = value

        if "segment_name" in segment_data and "sequence" in segment_data:
            self.add_node(
                node.Node(
                    segment_data["segment_name"],
                    segment_data["sequence"],
                    len(segment_data["sequence"]),
                    opt_fields={k: v for k, v in segment_data.items() if k not in ["segment_name", "sequence"]},
                )
            )

    def _process_link_line(self, child, line_num: int, logger) -> None:
        """Process a parsed link line and add it to the graph.

        :param child: The parsed link line from lark.
        :param line_num: The line number for logging.
        :param logger: The logger instance.
        """
        link_data: dict[str, Any] = {}
        for link_child in child.children:
            if link_child.data == "segment_from":
                link_data["from_node"] = link_child.children[0].value
                logger.debug(f"From node: {link_data['from_node']}")
            elif link_child.data == "orientation_from":
                link_data["from_orn"] = link_child.children[0].value
                logger.debug(f"From orientation: {link_data['from_orn']}")
            elif link_child.data == "segment_to":
                link_data["to_node"] = link_child.children[0].value
                logger.debug(f"To node: {link_data['to_node']}")
            elif link_child.data == "orientation_to":
                link_data["to_orn"] = link_child.children[0].value
                logger.debug(f"To orientation: {link_data['to_orn']}")
            elif link_child.data == "link_overlap":
                link_data["alignment"] = link_child.children[0].value
                logger.debug(f"Alignment: {link_data['alignment']}")
            elif link_child.data == "optional_field":
                tag = link_child.children[0].children[0].value
                _ = link_child.children[1].children[0].value  # value_type
                value = link_child.children[2].children[0].value
                link_data[tag] = value
                logger.debug(f"Optional field: {tag}={value}")

        if all(k in link_data for k in ["from_node", "from_orn", "to_node", "to_orn", "alignment"]):
            logger.debug(f"Adding edge: {link_data['from_node']} -> {link_data['to_node']}")
            self.add_edge(
                ge.Edge(
                    None,  # eid
                    link_data["from_node"],
                    link_data["from_orn"],
                    link_data["to_node"],
                    link_data["to_orn"],
                    (None, None),  # from_positions
                    (None, None),  # to_positions
                    link_data["alignment"],
                    None,  # distance
                    None,  # variance
                    opt_fields={
                        k: v
                        for k, v in link_data.items()
                        if k not in ["from_node", "from_orn", "to_node", "to_orn", "alignment"]
                    },
                )
            )

    def _process_path_line(self, child) -> None:
        """Process a parsed path line and add it to the graph.

        :param child: The parsed path line from lark.
        """
        path_data: dict[str, Any] = {}
        for path_child in child.children:
            if path_child.data == "pathname":
                path_data["path_name"] = path_child.children[0].value
            elif path_child.data == "segment_list":
                # Extract oriented segments
                segments: list[str] = []
                for seg_child in path_child.children:
                    if hasattr(seg_child, "children"):
                        if len(seg_child.children) == 2:
                            seg_name = seg_child.children[0].value
                            orn = seg_child.children[1].value
                            segments.append(f"{seg_name}{orn}")
                path_data["segments"] = segments
            elif path_child.data == "overlap_list":
                # Extract overlaps
                overlaps: list[str] = []
                for ov_child in path_child.children:
                    if hasattr(ov_child, "children") and ov_child.children:
                        overlaps.append(ov_child.children[0].value)
                path_data["overlaps"] = overlaps
            elif path_child.data == "optional_field":
                tag = path_child.children[0].children[0].value
                _ = path_child.children[1].children[0].value  # value_type
                value = path_child.children[2].children[0].value
                path_data[tag] = value

        if "path_name" in path_data and "segments" in path_data:
            self.add_path(path_data)

    def _process_walk_line(self, child) -> None:
        """Process a parsed walk line and add it to the graph.

        :param child: The parsed walk line from lark.
        """
        walk_data: dict[str, Any] = {}
        for walk_child in child.children:
            if walk_child.data == "sample_id":
                walk_data["sample_id"] = walk_child.children[0].value
            elif walk_child.data == "hapindex":
                walk_data["hapindex"] = int(walk_child.children[0].value)
            elif walk_child.data == "seq_id":
                walk_data["seq_id"] = walk_child.children[0].value
            elif walk_child.data == "seq_start":
                value = walk_child.children[0].value
                walk_data["seq_start"] = None if value == "*" else int(value)
            elif walk_child.data == "seq_end":
                value = walk_child.children[0].value
                walk_data["seq_end"] = None if value == "*" else int(value)
            elif walk_child.data == "walk":
                walk_data["walk"] = walk_child.children[0].value
            elif walk_child.data == "optional_field":
                tag = walk_child.children[0].children[0].value
                _ = walk_child.children[1].children[0].value  # value_type
                value = walk_child.children[2].children[0].value
                walk_data[tag] = value

        if "sample_id" in walk_data and "walk" in walk_data:
            self.add_walk(walk_data)
