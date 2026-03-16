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

from pygfa.exceptions import GFAError
from pygfa.gfa.base import BaseGFA, Element
from pygfa.graph_element import edge as ge
from pygfa.graph_element import node
from pygfa.graph_element import subgraph as sg
from pygfa.utils.file_opener import open_gfa_file

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
            if line_.startswith("#"):
                logger.debug(f"Skipping comment line {i + 1}")
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
                            self._process_containment_line(child, i, logger)
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
                    link_data.get("ID"),  # eid
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

    def _process_containment_line(self, child, line_num: int, logger) -> None:
        """Process a parsed containment line and add it to the graph.

        :param child: The parsed containment line from lark.
        :param line_num: The line number for logging.
        :param logger: The logger instance.
        """
        containment_data: dict[str, Any] = {}
        segment_names = []
        orientations = []

        for containment_child in child.children:
            if hasattr(containment_child, "data"):
                if containment_child.data == "segment_name":
                    segment_names.append(containment_child.children[0].value)
                elif containment_child.data == "position":
                    containment_data["pos"] = containment_child.children[0].value
                    logger.debug(f"Position: {containment_data['pos']}")
                elif containment_child.data == "cigar":
                    containment_data["alignment"] = containment_child.children[0].value
                    logger.debug(f"Alignment: {containment_data['alignment']}")
                elif containment_child.data == "optional_field":
                    tag = containment_child.children[0].children[0].value
                    _ = containment_child.children[1].children[0].value  # value_type
                    value = containment_child.children[2].children[0].value
                    containment_data[tag] = value
                    logger.debug(f"Optional field: {tag}={value}")
            else:
                # It's a Token (orientation)
                orientations.append(str(containment_child))

        # Assign segment names and orientations
        if len(segment_names) >= 2:
            containment_data["from_node"] = segment_names[0]
            containment_data["to_node"] = segment_names[1]
            logger.debug(f"From node: {containment_data['from_node']}")
            logger.debug(f"To node: {containment_data['to_node']}")
        if len(orientations) >= 2:
            containment_data["from_orn"] = orientations[0]
            containment_data["to_orn"] = orientations[1]
            logger.debug(f"From orientation: {containment_data['from_orn']}")
            logger.debug(f"To orientation: {containment_data['to_orn']}")

        if all(k in containment_data for k in ["from_node", "from_orn", "to_node", "to_orn", "pos", "alignment"]):
            logger.debug(f"Adding containment edge: {containment_data['from_node']} -> {containment_data['to_node']}")
            self.add_edge(
                ge.Edge(
                    containment_data.get("ID"),  # eid
                    containment_data["from_node"],
                    containment_data["from_orn"],
                    containment_data["to_node"],
                    containment_data["to_orn"],
                    (None, None),  # from_positions
                    (None, None),  # to_positions
                    containment_data["alignment"],
                    None,  # distance
                    None,  # variance
                    opt_fields={
                        k: v
                        for k, v in containment_data.items()
                        if k not in ["from_node", "from_orn", "to_node", "to_orn", "alignment", "pos"]
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

    @classmethod
    def from_gfa(cls, filepath):
        """Parse the given file and return a GFA object.

        Since GFA is a line-oriented format, we can parse each line separately.
        This allows to avoid keeping the entire parse tree in memory.

        :param filepath: Path to the GFA file.
        :returns: A new GFA graph object.
        """
        logger = logging.getLogger(__name__)
        logger.debug(f"GFA.from_gfa(): Starting to parse file: {filepath}")

        g = cls()

        # Load the grammar from the gfa.lark file
        grammar_file = os.path.join(os.path.dirname(__file__), "..", "graph_element", "parser", "gfa.lark")
        logger.debug(f"Loading grammar from: {grammar_file}")
        with open(grammar_file) as f:
            grammar = f.read()
        logger.debug(f"Grammar loaded, size: {len(grammar)} characters")

        # Create the parser
        parser = lark.Lark(grammar, start="start")
        logger.debug("Lark parser created")

        # Read and parse the file line by line
        line_count = 0
        with open_gfa_file(filepath) as f:
            for line in f:
                line = line.strip()
                line_count += 1
                if not line or line.startswith("#"):
                    continue

                try:
                    # Parse the line using from_string logic
                    tree = parser.parse(line + "\n")
                    logger.debug(f"Line {line_count}: Successfully parsed")

                    # Process the parsed tree based on line type
                    for subtree in tree.children:
                        for child in subtree.children:
                            if child.data == "header_line":
                                pass
                            elif child.data == "segment_line":
                                g._process_segment_line(child)
                            elif child.data == "link_line":
                                g._process_link_line(child, line_count, logger)
                            elif child.data == "containment_line":
                                g._process_containment_line(child, line_count, logger)
                            elif child.data == "path_line":
                                g._process_path_line(child)
                            elif child.data == "walk_line":
                                g._process_walk_line(child)

                except lark.exceptions.LarkError as e:
                    logger.warning(
                        f"Failed to parse line {line_count}: {line[:50]}{'...' if len(line) > 50 else ''} - {e}"
                    )
                    continue

        return g

    @classmethod
    def from_file(cls, filepath: str, **kwargs) -> "GFA":
        """Load a GFA graph from a file, auto-detecting format from extension.

        Supports both text GFA (plain, gzip, zstd, xz) and binary BGFA formats.

        :param filepath: Path to a .gfa, .gfa.gz, .gfa.zst, .gfa.xz, or .bgfa file.
        :param kwargs: Passed to the underlying reader (e.g. verbose, debug, logfile for BGFA).
        :return: GFA graph object.
        """
        # Strip compression suffixes to expose the base format extension
        name = filepath
        for suffix in (".gz", ".zst", ".zstd", ".xz"):
            if name.endswith(suffix):
                name = name[: -len(suffix)]
                break

        if name.endswith(".bgfa"):
            return cls.from_bgfa(filepath, **kwargs)
        else:
            return cls.from_gfa(filepath)

    @classmethod
    def from_bgfa(
        cls,
        file_path: str,
        verbose: bool = False,
        debug: bool = False,
        logfile: str = None,
    ) -> "GFA":
        """Read a BGFA file and return the corresponding GFA graph.

        :param file_path: Path to the BGFA file
        :param verbose: If True, log detailed information
        :param debug: If True, log debug information
        :param logfile: Path to log file (if None and verbose=True, uses a temporary file)
        :return: GFA graph object
        """
        from pygfa.bgfa import read_bgfa

        return read_bgfa(file_path, verbose=verbose, debug=debug, logfile=logfile)

    def pprint(self):
        """Pretty print the entire GFA graph, including all attributes."""
        print("=== GFA Graph ===")

        # Print header information
        print(f"Nodes: {len(self.nodes())}")
        print(f"Edges: {len(self.edges())}")
        print(f"Subgraphs: {len(self.subgraphs())}")
        print(f"Paths: {len(self.paths())}")
        print(f"Walks: {len(self.walks())}")
        print()

        # Print nodes
        if self.nodes():
            print("--- Nodes ---")
            for node_id, data in self.nodes_iter(data=True):
                print(f"  Node: {node_id}")
                for key, value in data.items():
                    if key not in ["nid", "sequence", "slen"]:
                        print(f"    {key}: {value}")
                if "sequence" in data:
                    print(f"    sequence: {data['sequence']}")
                # Print length field - use slen if available, otherwise calculate from sequence
                if "slen" in data:
                    print(f"    length: {data['slen']}")
                elif "sequence" in data and data["sequence"] != "*":
                    print(f"    length: {len(data['sequence'])}")
            print()

        # Print edges
        if self.edges():
            print("--- Edges ---")
            for u, v, key, data in self.edges_iter(data=True, keys=True):
                print(f"Edge: {key} ({u} -> {v})")
                for attr, val in data.items():
                    if attr not in ["from_node", "to_node", "eid"]:
                        print(f"     {attr}: {val}")
            print()

        # Print paths
        if self.paths():
            print("--- Paths ---")
            for path_id, path_data in self.paths_iter(data=True):
                print(f"  Path: {path_id}")
                for key, value in path_data.items():
                    print(f"    {key}: {value}")
            print()

        # Print walks
        if self.walks():
            print("--- Walks ---")
            for walk_id, walk_data in self.walks_iter(data=True):
                print(f"  Walk: {walk_id}")
                for key, value in walk_data.items():
                    print(f"    {key}: {value}")
            print()

        # Print subgraphs
        if self.subgraphs():
            print("--- Subgraphs ---")
            for sub_id, sub_data in self.subgraphs_iter(data=True):
                print(f"  Subgraph: {sub_id}")
                sub_dict = sub_data.as_dict()
                for key, value in sub_dict.items():
                    print(f"    {key}: {value}")
            print()

    def to_bgfa(
        self,
        file=None,
        block_size=1024,
        compression_options=None,
        verbose: bool = False,
        debug: bool = False,
        logfile: str = None,
        **kwargs,
    ) -> bytes:
        """Convert this GFA graph to BGFA binary format."""
        from pygfa.bgfa import to_bgfa as bgfa_to_bgfa

        return bgfa_to_bgfa(
            self,
            file=file,
            block_size=block_size,
            compression_options=compression_options,
            verbose=verbose,
            debug=debug,
            logfile=logfile,
            **kwargs,
        )

    def to_gfa(self):
        """Output a GFA string associated to this GFA graph.

        The elements appear in this order:
        1. Header
        2. Segments (sorted by name)
        3. Links (sorted by From, then To)
        4. Paths (sorted by PathName)
        5. Walks (sorted by SampleID, then SeqId)
        6. Containments (sorted by Container, then Contained)

        :returns: A string containing the GFA representation
        """
        logger = logging.getLogger(__name__)
        logger.debug("to_gfa(): Starting GFA serialization")

        lines = []

        # 1. Header
        lines.append("H\tVN:Z:1.0")
        logger.debug("to_gfa(): Added header")

        # 2. Segments (sorted by name)
        segments = []
        logger.debug(f"to_gfa(): Processing {len(list(self.nodes_iter()))} nodes")
        for node_id, data in self.nodes_iter(data=True):
            line_parts = ["S", node_id, data.get("sequence", "*")]
            # Add optional fields
            for key, value in data.items():
                if key not in ["nid", "sequence", "slen"]:
                    if isinstance(value, int):
                        line_parts.append(f"{key}:i:{value}")
                    elif isinstance(value, str):
                        line_parts.append(f"{key}:Z:{value}")
            segments.append("\t".join(line_parts))
        segments.sort(key=lambda x: x.split("\t")[1])
        lines.extend(segments)
        logger.debug(f"to_gfa(): Added {len(segments)} segments")

        # 3. Links (sorted by From, then To)
        links = []
        logger.debug(f"to_gfa(): Processing {len(list(self.edges_iter()))} edges")
        for u, v, _key, data in self.edges_iter(data=True, keys=True):
            from_node = data.get("from_node", u)
            from_orn = data.get("from_orn", "+")
            to_node = data.get("to_node", v)
            to_orn = data.get("to_orn", "+")
            alignment = data.get("alignment", "*")

            line_parts = ["L", from_node, from_orn, to_node, to_orn, alignment]

            # Add optional fields
            for field_name, value in data.items():
                if field_name not in [
                    "eid",
                    "from_node",
                    "from_orn",
                    "to_node",
                    "to_orn",
                    "alignment",
                    "distance",
                    "variance",
                    "from_positions",
                    "to_positions",
                    "from_segment_end",
                    "to_segment_end",
                ]:
                    if isinstance(value, int):
                        line_parts.append(f"{field_name}:i:{value}")
                    elif isinstance(value, str):
                        line_parts.append(f"{field_name}:Z:{value}")

            links.append("\t".join(line_parts))

        links.sort(key=lambda x: (x.split("\t")[2], x.split("\t")[4]))
        lines.extend(links)
        logger.debug(f"to_gfa(): Added {len(links)} links")

        # 4. Paths (sorted by PathName)
        paths = []
        logger.debug(f"to_gfa(): Processing {len(self._paths)} paths")
        for path_id, path_data in self.paths_iter(data=True):
            line_parts = ["P", path_id]

            # Add segments
            segments = path_data.get("segments", [])
            line_parts.append(",".join(segments))

            # Add overlaps
            overlaps = path_data.get("overlaps", [])
            if overlaps:
                line_parts.append(",".join(overlaps))

            # Add optional fields
            for key, value in path_data.items():
                if key not in ["path_name", "segments", "overlaps"]:
                    if isinstance(value, int):
                        line_parts.append(f"{key}:i:{value}")
                    elif isinstance(value, str):
                        line_parts.append(f"{key}:Z:{value}")

            paths.append("\t".join(line_parts))

        paths.sort(key=lambda x: x.split("\t")[1])
        lines.extend(paths)
        logger.debug(f"to_gfa(): Added {len(paths)} paths")

        # 5. Walks (sorted by SampleID, then SeqId)
        walks = []
        logger.debug(f"to_gfa(): Processing {len(self._walks)} walks")
        for _walk_id, walk_data in self.walks_iter(data=True):
            line_parts = ["W"]

            # Add required fields
            line_parts.append(walk_data.get("sample_id", ""))
            line_parts.append(str(walk_data.get("hapindex", 0)))
            line_parts.append(walk_data.get("seq_id", ""))

            # Add optional positions
            seq_start = walk_data.get("seq_start", "*")
            seq_end = walk_data.get("seq_end", "*")
            line_parts.append(str(seq_start) if seq_start is not None else "*")
            line_parts.append(str(seq_end) if seq_end is not None else "*")

            # Add walk string
            line_parts.append(walk_data.get("walk", ""))

            # Add optional fields
            for key, value in walk_data.items():
                if key not in [
                    "sample_id",
                    "hapindex",
                    "seq_id",
                    "seq_start",
                    "seq_end",
                    "walk",
                ]:
                    if isinstance(value, int):
                        line_parts.append(f"{key}:i:{value}")
                    elif isinstance(value, str):
                        line_parts.append(f"{key}:Z:{value}")

            walks.append("\t".join(line_parts))

        walks.sort(key=lambda x: (x.split("\t")[1], x.split("\t")[3]))
        lines.extend(walks)
        logger.debug(f"to_gfa(): Added {len(walks)} walks")

        # 6. Containments (sorted by Container, then Contained)
        # For now, containments are not fully supported
        # This would require parsing and storing containment lines

        result = "\n".join(lines)
        logger.debug(f"to_gfa(): GFA serialization complete, {len(result)} characters")
        return result
