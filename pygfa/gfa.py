"""
GFA representation through a networkx MulitGraph.
"""

import logging
import copy
import re
import os

try:
    import compression.zstd as z

    _ZSTD_AVAILABLE = True
except ImportError:
    _ZSTD_AVAILABLE = False
    z = None

import networkx as nx
from networkx.classes.function import all_neighbors as nx_all_neighbors
from itertools import islice

from pygfa.graph_element.parser import segment, link, containment, path
from pygfa.graph_element.parser import edge, gap, fragment, group
from pygfa.graph_element import node, edge as ge, subgraph as sg

from pygfa.graph_operations.compression import (
    compression_graph_by_nodes,
    compression_graph_by_edges,
)
from pygfa.graph_operations.overlap_consistency import check_overlap
from benchmark.extract_subgraph import extract_subgraph

from pygfa.encoding import (
    compress_integer_list_varint,
    compress_string_zstd,
    compress_string_gzip,
    compress_string_lzma,
    compress_string_none,
    compress_string_list,
)

# BGFAWriter is imported locally in the to_bgfa method to avoid circular imports

import lark

GRAPH_LOGGER = logging.getLogger(__name__)


class InvalidSearchParameters(Exception):
    pass


class InvalidElementError(Exception):
    pass


class GFAError(Exception):
    pass


class Element:
    """Represent the types of graph a GFA graph object can have."""

    NODE = 0
    EDGE = 1
    SUBGRAPH = 2


def _index(obj, other):
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


class GFA:
    """GFA will use a networkx MultiGraph as structure to contain
    the elements of the specification.
    GFA graphs directly accept only instances coming from the
    graph_elements package, but can contains any kind of data
    undirectly by accessing the `_graph` attribute.
    """

    def __init__(self, base_graph=None):
        """Creates a GFA graph.

        If :param base_graph: is not `None` use the graph provided
        as base for the graph.

        A `virtual id` is assigned to edges(graph edges) that don't
        have an id.
        Their id will be `virtual_#` where `#` will be given
        by `next_virtual_id`.

        :param base graph: An instance of a networkx.MultiGraph.
        """
        if base_graph is not None and not isinstance(base_graph, nx.MultiGraph):
            raise GFAError(
                f"{type(base_graph)} cannot be used as base graph, use networkx.MultiGraph instead."
            )
        self._graph = nx.MultiGraph(base_graph)
        self._subgraphs = {}
        self._next_virtual_id = 0 if base_graph is None else self._find_max_virtual_id()
        self._segment_map = {}
        self._paths = {}  # New attribute to store paths
        self._walks = {}  # New attribute to store walks
        self._header_info = {}  # Store BGFA header information

        # Initialize segment map from base_graph if provided
        if base_graph is not None and hasattr(base_graph, "_segment_map"):
            self._segment_map = base_graph._segment_map.copy()
        if base_graph is not None and hasattr(base_graph, "_header_info"):
            self._header_info = base_graph._header_info.copy()

    def __contains__(self, id_):
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

    def clear(self):
        """Clear all GFA object elements.

        Call networkx `clear` method, reset the virtual id counter and
        delete all the subgraphs.
        """
        self._graph.clear()
        self._next_virtual_id = 0
        self._subgraphs = {}
        self._paths = {}
        self._walks = {}

    def _get_virtual_id(self, increment=True):
        """Return the next virtual id value available.

        :param increment: If set to False, the virtual id is not
            incremented. Useful mainly in interactive mode.
        """
        key = self._next_virtual_id
        if increment:
            self._next_virtual_id += 1
        return key

    def _find_max_virtual_id(self):
        """Traverse the graph to find the greatest virtual id value."""
        # nodes cannot have a virtual_id, so don't search inside them
        virtual_rxp = r"^virtual_(\d+)$"
        regexp = re.compile(virtual_rxp)
        virtual_keys = [0]

        for from_node, to_node, key in self.edges_iter(keys=True):
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

    def nodes(self, data=False, with_sequence=False, identifier=None):
        """Return a list of the nodes in the graph.

        :param with_sequence: If set return only nodes with
            a `sequence` property.
        """
        # return list(self.nodes_iter(data=data, with_sequence=with_sequence))
        if identifier is not None:
            if self._graph.has_node(identifier):
                return self._graph.nodes(data=data)[identifier]
            else:
                return

        if with_sequence is True:
            return list(self.nodes_iter(data=data, with_sequence=with_sequence))

        return self._graph.nodes(data=data)

    def edges(self, identifier=None, adj_dict=False, **kwargs):
        """Return all the edges in the graph."""
        # return list(self._graph.edges(**kwargs))

        if identifier is not None:
            if isinstance(identifier, tuple):
                return self._search_edge_by_nodes(identifier)
            else:
                return self._search_edge_by_key(identifier)

        if adj_dict is True:
            return self._graph.adj

        return self._graph.edges(**kwargs)

    def subgraphs(self, identifier=None):
        """An interface to access to the subgraphs inside
        the GFA object.

        If `identifier` is `None` all the graph Subgraph objects are
        returned.
        """
        if identifier is None:
            return self._subgraphs
        else:
            if identifier in self._subgraphs:
                return self._subgraphs[identifier]

    def paths(self, identifier=None):
        """An interface to access to the paths inside
        the GFA object.

        If `identifier` is `None` all the path objects are
        returned.
        """
        if identifier is None:
            return self._paths
        else:
            if identifier in self._paths:
                return self._paths[identifier]

    def walks(self, identifier=None):
        """An interface to access to the walks inside
        the GFA object.

        If `identifier` is `None` all the walk objects are
        returned.
        """
        if identifier is None:
            return self._walks
        else:
            if identifier in self._walks:
                return self._walks[identifier]

    def _search_edge_by_key(self, edge_key):
        from_node, to_node = self._get_edge_end_nodes(edge_key)
        if (from_node, to_node) != (None, None):
            return self._graph.get_edge_data(from_node, to_node, edge_key)
        return None

    def _search_edge_by_nodes(self, nodes):
        """Search for edge and edges providing end nodes.

        If given a tuple with from_node and to_node return all the edges
        between the two nodes.

        If a third element is present in the tuple return the exact edge
        between the two nodes with the key specified by the third element.
        If no match is found return `None`.

        :returns list of dictionary: If `nodes` is a two element tuple.
        :returns dictionary: Otherwise.
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

    def _get_edge_end_nodes(self, edge_key):
        """Given an edge key return a tuple that contains
        the end nodes for that edge.
        """
        for from_node, to_node, key in self.edges_iter(keys=True):
            if key == edge_key:
                return from_node, to_node
        return None, None

    def get(self, key):
        """Return the element pointed by the specified key."""
        if self._graph.has_node(key):
            return self.nodes(data=True, identifier=key)
        if key in self._subgraphs:
            return self._subgraphs[key]
        if key in self._paths:
            return self._paths[key]
        if key in self._walks:
            return self._walks[key]
        edge_ = self._search_edge_by_key(key)
        if not edge_ is None:
            return edge_

    def as_graph_element(self, key):
        """Given a key of an existing node, edge or subgraph, return
        its equivalent graph element object.
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
                    is_dovetail=element["is_dovetail"],
                )
                return edge_
        except KeyError:
            return None

    def add_graph_element(self, element):
        """Add a graph element -Node, Edge or Subgraph- object to
        the graph."""
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

    def add_node(self, new_node, safe=False):
        """Add a graph_element Node to the GFA graph
        using the node id as key.

        Its sequence and sequence length will be individual attributes
        on the graph and all the remainders optional field will be stored
        individually as node data.

        :param new_node: A graph_element.Node object or a string
            that can represent a node (such as the Segment line).
        :param safe: If set check if the given identifier has already
            been added to the graph, and in that case raise
            an exception
        """
        if isinstance(new_node, str) and new_node[0] == "S":
            new_node = node.Node.from_line(
                segment.SegmentV1.from_string(new_node.strip())
            )

        if not node.is_node(new_node):
            raise node.InvalidNodeError("The object given is not a node.")

        if safe and new_node.nid in self:
            raise GFAError("An element with the same id already exists.")

        self._graph.add_node(
            new_node.nid,
            nid=new_node.nid,
            sequence=new_node.sequence,
            slen=new_node.slen,
            **new_node.opt_fields,
        )
        return True

    def remove_node(self, nid):
        """Remove a node with nid as its node id.

        Edges containing nid as end node will be automatically
        deleted.

        :param nid: The id belonging to the node to delete.
        :raise InvalidNodeError: If `nid` doesn't point to any node.
        """
        try:
            self._graph.remove_node(nid)
        except Exception:
            raise node.InvalidNodeError(
                f"{nid} doesn't point to any node in the graph."
            )

    def nodes_iter(self, data=False, with_sequence=False):
        """Return an iterator over nodes in the graph.

        :para with_sequence: If set return only nodes with
            a sequence property.
        """
        if with_sequence is True:
            if data is True:
                return iter(
                    (nid, data_)
                    for nid, data_ in self._graph.nodes(data=True)
                    if "sequence" in data_
                )
            else:
                return iter(
                    nid
                    for nid, data_ in self._graph.nodes(data=True)
                    if "sequence" in data_
                )
        else:
            return iter(list(self._graph.nodes(data=data)))

    def nbunch_iter(self, nbunch=None):
        """Return an iterator of nodes contained in nbunch that are
        also in the graph.

        Interface to the networkx method.
        """
        return self._graph.nbunch_iter(nbunch=nbunch)

    def add_edge(self, new_edge, safe=False):
        """Add a graph_element Edge or a networkx edge to the GFA
        graph using  the edge id as key.

        If its id is `*` or `None` the edge will be given a
        **virtual_id**, in either case the original edge id will
        be preserved as edge attribute.

        All edge attributes will be stored as netwrorkx edge
        attributes and  all the remainders optional field will be stored
        individually as edge data.
        """
        if isinstance(new_edge, str):
            if new_edge[0] == "L":
                new_edge = ge.Edge.from_line(link.Link.from_string(new_edge.strip()))
            elif new_edge[0] == "C":
                new_edge = ge.Edge.from_line(
                    containment.Containment.from_string(new_edge.strip())
                )
            elif new_edge[0] == "E":
                new_edge = ge.Edge.from_line(edge.Edge.from_string(new_edge.strip()))
            elif new_edge[0] == "G":
                new_edge = ge.Edge.from_line(gap.Gap.from_string(new_edge.strip()))
            elif new_edge[0] == "F":
                new_edge = ge.Edge.from_line(
                    fragment.Fragment.from_string(new_edge.strip())
                )
            else:
                raise ge.InvalidEdgeError(
                    f"The string given doesn't represent a GFA line that could"
                    f" be represented as an edge,\n"
                    f"given: {new_edge}"
                )

        if not ge.is_edge(new_edge):
            raise ge.InvalidEdgeError("The object is not a valid edge.")

        key = new_edge.eid
        if new_edge.eid is None or new_edge.eid == "*":
            key = f"virtual_{self._get_virtual_id()}"

        if safe:
            edge_exists = key in self
            node1_exists = new_edge.from_node in self
            node2_exists = new_edge.to_node in self
            if edge_exists:
                raise GFAError("An element with the same id already exists.")
            if not (node1_exists and node2_exists):
                raise GFAError("From/To node are not already in the graph.")

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
            is_dovetail=new_edge.is_dovetail,
            from_segment_end=new_edge.from_segment_end,
            to_segment_end=new_edge.to_segment_end,
            **new_edge.opt_fields,
        )

    def remove_edge(self, identifier):
        """Remove an edge or all edges identified by an id
        or by a tuple with end node, respectively.

        * If `identifier` is a two elements tuple remove all the
            all the edges between the two nodes.

        * If `identifier` is a three elements tuple remove the edge
            specified by the third element of the tuple with end nodes
            given by the first two elements of the tuple itself.

        * If `identifier` is not a tuple, treat it as it should be
            an edge id.

        :raise InvalidEdgeError: If `identifier` is not in the cases
            described above.
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
            raise ge.InvalidEdgeError(nxe)

    def remove_edges(self, from_node, to_node):
        """Remove all the direct edges between the two nodes given.

        Call iteratively remove_edge (remove a not specified edge
        from `from_node` and `to_node`) for n-times where n is
        the number of edges between the given nodes,
        removing all the edges indeed.
        """
        num_edges = len(self.edges(identifier=(from_node, to_node)))
        for edge_ in range(0, num_edges):
            self._graph.remove_edge(from_node, to_node)

    def edges_iter(self, nbunch=None, data=False, keys=False, default=None):
        """Interface to networx edges iterator."""
        return iter(
            self._graph.edges(nbunch=nbunch, data=data, keys=keys, default=default)
        )

    def add_subgraph(self, subgraph, safe=False):
        """Add a Subgraph object to the graph.

        The object is not altered in any way.
        A deepcopy of the object given is attached to the graph.
        """
        if isinstance(subgraph, str):
            if subgraph[0] == "P":
                subgraph = sg.Subgraph.from_line(path.Path.from_string(subgraph))
            elif subgraph[0] == "O":
                subgraph = sg.Subgraph.from_line(group.OGroup.from_string(subgraph))
            elif subgraph[0] == "U":
                subgraph = sg.Subgraph.from_line(group.UGroup.from_string(subgraph))
            else:
                raise sg.InvalidSubgraphError(
                    f"The string given cannot be represented as a subgraph,\ngiven: {subgraph}"
                )
        if not sg.is_subgraph(subgraph):
            raise sg.InvalidSubgraphError("The object given is not a subgraph.")

        key = subgraph.sub_id
        if key == "*":
            key = f"virtual_{self._get_virtual_id()}"
        if safe and key in self:
            raise GFAError("An element with the same id already exists.")
        self._subgraphs[key] = copy.deepcopy(subgraph)

    def remove_subgraph(self, subgraph_id):
        """Remove the Subgraph object identified by the given id."""
        try:
            del self._subgraphs[subgraph_id]
        except Exception:
            raise sg.InvalidSubgraphError(
                "The given id doesn't " + " identify any subgraph."
            )

    def subgraphs_iter(self, data=False):
        """Return an iterator over subgraphs elements
        in the GFA graph.
        """
        if data is True:
            return iter(self._subgraphs.items())
        else:
            return iter(self._subgraphs)

    def add_path(self, path_data, safe=False):
        """Add a path to the graph.

        The path_data should be a dictionary with:
        - 'path_name': the name of the path
        - 'segments': list of oriented segments (e.g., ['s1+', 's2-'])
        - 'overlaps': optional list of overlaps between segments
        - any optional fields

        :param path_data: Dictionary containing path information
        :param safe: If set, check if the path id already exists
        """
        if isinstance(path_data, str):
            if path_data[0] == "P":
                # Parse the path line
                path_obj = path.Path.from_string(path_data.strip())
                # Convert to dictionary format
                path_data = {
                    "path_name": path_obj.fields["path_name"].value,
                    "segments": path_obj.fields["seqs_names"].value,
                    "overlaps": (
                        path_obj.fields["overlaps"].value
                        if "overlaps" in path_obj.fields
                        else []
                    ),
                }
                # Add optional fields
                for field_name, field in path_obj.fields.items():
                    if field_name not in ["path_name", "seqs_names", "overlaps"]:
                        path_data[field_name] = field.value

        if not isinstance(path_data, dict) or "path_name" not in path_data:
            raise GFAError("Invalid path data format.")

        key = path_data["path_name"]
        if key == "*":
            key = f"virtual_{self._get_virtual_id()}"
        if safe and key in self._paths:
            raise GFAError("A path with the same id already exists.")

        # Store the path data
        self._paths[key] = copy.deepcopy(path_data)

    def remove_path(self, path_id):
        """Remove the path identified by the given id."""
        try:
            del self._paths[path_id]
        except Exception:
            raise GFAError("The given id doesn't identify any path.")

    def paths_iter(self, data=False):
        """Return an iterator over paths in the GFA graph."""
        if data is True:
            return iter(self._paths.items())
        else:
            return iter(self._paths)

    def add_walk(self, walk_data, safe=False):
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
        """
        if isinstance(walk_data, str):
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
            raise GFAError("Invalid walk data format.")

        # Create a unique key for the walk
        key = f"{walk_data['sample_id']}_{walk_data['hapindex']}_{walk_data['seq_id']}"
        if safe and key in self._walks:
            raise GFAError("A walk with the same id already exists.")

        # Store the walk data
        self._walks[key] = copy.deepcopy(walk_data)

    def remove_walk(self, walk_id):
        """Remove the walk identified by the given id."""
        try:
            del self._walks[walk_id]
        except Exception:
            raise GFAError("The given id doesn't identify any walk.")

    def walks_iter(self, data=False):
        """Return an iterator over walks in the GFA graph."""
        if data is True:
            return iter(self._walks.items())
        else:
            return iter(self._walks)

    def get_subgraph(self, sub_key):
        """Return a GFA subgraph from the parent graph.

        Return a new GFA graph structure with the nodes,
        edges and subgraphs specified in the elements attributes
        of the subgraph object pointed by the id.

        The returned GFA is *independent* from the original object.

        :param sub_key: The id of a subgraph present in the GFA graph.
        :returns None: If the subgraph id doesn't exist.
        """
        if not sub_key in self._subgraphs:
            raise sg.InvalidSubgraphError("There is no subgraph pointed by this key.")
        subgraph = self._subgraphs[sub_key]
        sub_gfa = GFA()
        for id_ in subgraph.elements.keys():
            # creating a new GFA graph and the add method,
            # the virtual id are recomputed
            sub_gfa.add_graph_element(self.as_graph_element(id_))
        return sub_gfa

    def subgraph(self, nbunch, copy=True):
        """Given a bunch of nodes return a graph with
        all the given nodes and the edges between them.

        The returne object is not a GFA Graph, but a
        MultiGraph. To create a new GFA graph, just
        use the GFA initializer an give the subgraph to it.

        Interface to the networkx subgraph method.
        Given a collection of nodes return a subgraph with the nodes
        given and all the edges between each pair of nodes.

        :param nbunch: The nodes.
        :param copy: If set to True return a copy of the subgraph.
        """
        subgraph_ = self._graph.subgraph(nbunch)
        if copy:
            return subgraph_.copy()
        return subgraph_

    def neighbors(self, nid):
        """Return all the nodes id of the nodes connected to
        the given node.

        Return all the predecessors and successors of the
        given source node.

        :params nid: The id of the selected node
        """
        if self.nodes(identifier=nid) is None:
            raise GFAError("The source node is not in the graph.")
        return list(nx_all_neighbors(self._graph, nid))

    def search(self, comparator, limit_type=None):
        """Perform a query applying the comparator on each graph element."""
        if limit_type == Element.NODE:
            return self.search_on_nodes(comparator)

        elif limit_type == Element.EDGE:
            return self.search_on_edges(comparator)

        elif limit_type == Element.SUBGRAPH:
            return self.search_on_subgraph(comparator)

        retval = []
        retval.extend(self.search_on_nodes(comparator))
        retval.extend(self.search_on_edges(comparator))
        retval.extend(self.search_on_subgraph(comparator))
        return retval

    def search_on_nodes(self, comparator):
        retval = []
        for key, data in self.nodes_iter(data=True):
            try:
                if comparator(data):
                    retval.append(key)
            except KeyError:
                pass
        return retval

    def search_on_edges(self, comparator):
        retval = []
        for _u, _v, key, data in self.edges_iter(data=True, keys=True):
            try:
                if comparator(data):
                    retval.append(key)
            except KeyError:
                pass
        return retval

    def search_on_subgraph(self, comparator):
        retval = []
        for key, data in self._subgraphs.items():
            data = data.as_dict()
            try:
                if comparator(data):
                    retval.append(key)
            except KeyError:
                pass
        return retval

    def from_string(self, string):
        """Add a GFA string to the graph once it has been
        converted.
        """
        lines = re.split("\n", string)

        # Load the grammar from the gfa.lark file
        grammar_file = os.path.join(
            os.path.dirname(__file__), "graph_element", "parser", "gfa.lark"
        )
        with open(grammar_file, "r") as f:
            grammar = f.read()

        # Create the parser
        parser = lark.Lark(grammar, start="start")
        # AI! add a logging.debug instruction for each step in this function

        for line_ in lines:
            line_ = line_.strip()
            if len(line_) < 1:
                continue

            try:
                # Parse the line
                tree = parser.parse(line_ + "\n")

                # Process the parsed tree based on line type
                for subtree in tree.children:
                    for child in subtree.children:
                        if child.data == "header_line":
                            # Handle header line
                            pass
                        elif child.data == "segment_line":
                            # Handle segment line
                            segment_data = {}
                            for seg_child in child.children:
                                if seg_child.data == "segment_name":
                                    segment_data["segment_name"] = seg_child.children[
                                        0
                                    ].value
                                elif seg_child.data == "seq_string":
                                    segment_data["sequence"] = seg_child.children[
                                        0
                                    ].value
                                elif seg_child.data == "optional_field":
                                    # Handle optional fields
                                    tag = seg_child.children[0].children[0].value
                                    value_type = seg_child.children[1].children[0].value
                                    value = seg_child.children[2].children[0].value
                                    segment_data[tag] = value

                            if (
                                "segment_name" in segment_data
                                and "sequence" in segment_data
                            ):
                                self.add_node(
                                    node.Node(
                                        segment_data["segment_name"],
                                        segment_data["sequence"],
                                        len(segment_data["sequence"]),
                                        opt_fields={
                                            k: v
                                            for k, v in segment_data.items()
                                            if k not in ["segment_name", "sequence"]
                                        },
                                    )
                                )

                        elif child.data == "link_line":
                            # Handle link line
                            logger.debug(f"Processing link line at line {i+1}")
                            link_data = {}
                            for link_child in child.children:
                                if link_child.data == "segment_from":
                                    link_data["from_node"] = link_child.children[
                                        0
                                    ].value
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
                                    link_data["alignment"] = link_child.children[
                                        0
                                    ].value
                                    logger.debug(f"Alignment: {link_data['alignment']}")
                                elif link_child.data == "optional_field":
                                    # Handle optional fields
                                    tag = link_child.children[0].children[0].value
                                    value_type = (
                                        link_child.children[1].children[0].value
                                    )
                                    value = link_child.children[2].children[0].value
                                    link_data[tag] = value
                                    logger.debug(f"Optional field: {tag}={value}")

                            if all(
                                k in link_data
                                for k in [
                                    "from_node",
                                    "from_orn",
                                    "to_node",
                                    "to_orn",
                                    "alignment",
                                ]
                            ):
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
                                            if k
                                            not in [
                                                "from_node",
                                                "from_orn",
                                                "to_node",
                                                "to_orn",
                                                "alignment",
                                            ]
                                        },
                                        is_dovetail=True,
                                    )
                                )

                        elif child.data == "containment_line":
                            # Handle containment line
                            pass

                        elif child.data == "path_line":
                            # Handle path line by adding it as a path
                            path_data = {}
                            for path_child in child.children:
                                if path_child.data == "pathname":
                                    path_data["path_name"] = path_child.children[
                                        0
                                    ].value
                                elif path_child.data == "segment_list":
                                    # Extract oriented segments
                                    segments = []
                                    for seg_child in path_child.children:
                                        if hasattr(seg_child, "children"):
                                            # Handle oriented_segment_sign or oriented_segment_char
                                            if len(seg_child.children) == 2:
                                                seg_name = seg_child.children[0].value
                                                orn = seg_child.children[1].value
                                                segments.append(f"{seg_name}{orn}")
                                    path_data["segments"] = segments
                                elif path_child.data == "overlap_list":
                                    # Extract overlaps
                                    overlaps = []
                                    for ov_child in path_child.children:
                                        if (
                                            hasattr(ov_child, "children")
                                            and ov_child.children
                                        ):
                                            overlaps.append(ov_child.children[0].value)
                                    path_data["overlaps"] = overlaps
                                elif path_child.data == "optional_field":
                                    # Handle optional fields
                                    tag = path_child.children[0].children[0].value
                                    value_type = (
                                        path_child.children[1].children[0].value
                                    )
                                    value = path_child.children[2].children[0].value
                                    path_data[tag] = value

                            if "path_name" in path_data and "segments" in path_data:
                                self.add_path(path_data)

                        elif child.data == "walk_line":
                            # Handle walk line
                            walk_data = {}
                            for walk_child in child.children:
                                if walk_child.data == "sample_id":
                                    walk_data["sample_id"] = walk_child.children[
                                        0
                                    ].value
                                elif walk_child.data == "hapindex":
                                    walk_data["hapindex"] = int(
                                        walk_child.children[0].value
                                    )
                                elif walk_child.data == "seq_id":
                                    walk_data["seq_id"] = walk_child.children[0].value
                                elif walk_child.data == "seq_start":
                                    value = walk_child.children[0].value
                                    walk_data["seq_start"] = (
                                        None if value == "*" else int(value)
                                    )
                                elif walk_child.data == "seq_end":
                                    value = walk_child.children[0].value
                                    walk_data["seq_end"] = (
                                        None if value == "*" else int(value)
                                    )
                                elif walk_child.data == "walk":
                                    walk_data["walk"] = walk_child.children[0].value
                                elif walk_child.data == "optional_field":
                                    # Handle optional fields
                                    tag = walk_child.children[0].children[0].value
                                    value_type = (
                                        walk_child.children[1].children[0].value
                                    )
                                    value = walk_child.children[2].children[0].value
                                    walk_data[tag] = value

                            if "sample_id" in walk_data and "walk" in walk_data:
                                self.add_walk(walk_data)

                        elif child.data == "jump_line":
                            # Handle jump line
                            pass

            except lark.exceptions.LarkError as e:
                # Skip lines that don't parse correctly
                continue

    def header(self, block_size=1024):
        """Generate the header corresponding to a graph.

        According to the BGFA specification:
        version (uint16)
        S_len (uint64) - Number of Segments
        L_len (uint64) - Number of Links
        P_len (uint64) - Number of Paths
        W_len (uint64) - Number of Walks
        S_offset (uint64) - offset to first segment block
        L_offset (uint64) - offset to first link block
        P_offset (uint64) - offset to first path block
        W_offset (uint64) - offset to first walk block
        block_size (uint16) - number of objects stored in each block
        header (C string) - GFA header text
        """
        # For now, we'll use version 1
        version = 1

        # Counts
        s_len = len(self.nodes())
        l_len = len(self.edges())
        p_len = len(self.paths())
        w_len = len(self.walks())

        # Offsets will be calculated later when writing the full file
        # For now, set them to 0
        s_offset = 0
        l_offset = 0
        p_offset = 0
        w_offset = 0

        # Header text from GFA
        header_text = "H\tVN:Z:1.0"

        header = bytes(
            b"".join(
                [
                    version.to_bytes(2, byteorder="big", signed=False),
                    s_len.to_bytes(8, byteorder="big", signed=False),
                    l_len.to_bytes(8, byteorder="big", signed=False),
                    p_len.to_bytes(8, byteorder="big", signed=False),
                    w_len.to_bytes(8, byteorder="big", signed=False),
                    s_offset.to_bytes(8, byteorder="big", signed=False),
                    l_offset.to_bytes(8, byteorder="big", signed=False),
                    p_offset.to_bytes(8, byteorder="big", signed=False),
                    w_offset.to_bytes(8, byteorder="big", signed=False),
                    block_size.to_bytes(2, byteorder="big", signed=False),
                    header_text.encode("ascii") + b"\0",
                ]
            )
        )
        logging.info(f"header,{len(header)},{len(header)}")

        return header

    def set_segment_map(self, map):
        """Set the segment map for the graph.

        :param map: A dictionary that maps node ids to segment ids.
        """
        if not isinstance(map, dict):
            raise TypeError("The segment map must be a dictionary.")
        self._segment_map = map

    def get_segment_id(self, segment_id):
        """Get the segment id for a given node id.

        :param segment_id: The node id to get the segment id for.
        :returns: The segment id if it exists, otherwise None.
        """
        if not hasattr(self, "_segment_map"):
            return None
        return self._segment_map.get(segment_id, None)

    def names_block(self, names, compression_level=19):
        compressed_names = z.compress(
            b"".join([name.encode(encoding="ascii") for name in names]),
            level=compression_level,
        )
        # header

        return bytes(
            b"".join(
                [
                    int(len(list(names))).to_bytes(
                        2, byteorder="big", signed=False
                    ),  ## block size
                    int(len(compressed_names)).to_bytes(
                        8, byteorder="big", signed=False
                    ),  ## size compressed names
                    int(sum([len(name) + 1 for name in names])).to_bytes(
                        8, byteorder="big", signed=False
                    ),  # length uncompressed names
                    compressed_names,
                ]
            )
        )

    def names_blocks(self, block_size=1024):
        n = len(self.nodes())
        self.set_segment_map(dict(zip([v for v in self.nodes()], range(1, n + 1))))
        # it = self.nodes_iter(data=True, with_sequence=True)
        it = self.nodes_iter()
        return bytes(
            b"".join(
                [
                    self.names_block(islice(it, block_size))
                    for _ in range((n + block_size - 1) // block_size)
                ]
            )
        )

    def segments_block(
        self, first, last, compression_method="zstd", compression_level=19
    ):
        """Extract a portion of the segments, with index from first to last (last excluded)
        and compute the corresponding segment block, according to the specification at
        https://github.com/AlgoLab/bgfatools/blob/main/spec/gfa_binary_format.md
        """
        # Get all nodes and slice the portion we need
        all_nodes = list(self.nodes_iter(data=True))
        nodes_slice = all_nodes[first:last]

        # Calculate block size (number of segments in this block)
        block_size = len(nodes_slice)

        # Prepare segment data
        segment_data = []
        for node_data in nodes_slice:
            # Get node information
            node_id = node_data[0]  # node identifier
            node_attrs = node_data[1]  # node attributes

            # Get sequence and length
            sequence = node_attrs.get("sequence", "")
            sequence_length = node_attrs.get("slen", len(sequence))

            # Convert sequence to bytes using the specified compression method
            sequence_bytes = compress_string_list(
                [sequence],
                compress_integer_list=compress_integer_list_varint,
                compression_method=compression_method,
                compression_level=compression_level,
            )

            # Create segment entry according to binary format:
            # segment_id (uint64) | sequence_length (uint64) | sequence (variable length)
            segment_entry = (
                self.get_segment_id(node_id).to_bytes(8, byteorder="big", signed=False)
                + sequence_length.to_bytes(8, byteorder="big", signed=False)
                + sequence_bytes
            )
            segment_data.append(segment_entry)

        # Create the complete segment block:
        # block_size (uint16) | segment_entries...
        block = block_size.to_bytes(2, byteorder="big", signed=False) + b"".join(
            segment_data
        )

        return block

    def segments_blocks(
        self, block_size=1024, compression_method="zstd", compression_level=19
    ):
        n = len(self.nodes())
        self.set_segment_map(dict(zip([v for v in self.nodes()], range(1, n + 1))))

        # Get all nodes as a list for proper slicing
        all_nodes = list(self.nodes_iter(data=True))

        # Process nodes in blocks
        blocks = []
        for i in range(0, n, block_size):
            first = i
            last = min(i + block_size, n)
            block = self.segments_block(
                first, last, compression_method, compression_level
            )
            blocks.append(block)

        return bytes(b"".join(blocks))

    def links_block(self, names, compression_level=19):
        return bytes(b"")

    def links_blocks(self, block_size=1024):
        """
        Compute the binary representation of the links of the graph, one block at a time.
        Each block contains a fixed number of links, specified by `block_size`.
        """
        n = len(self.edges())
        self.set_segment_map(dict(zip([v for v in self.edges()], range(1, n + 1))))
        it = self.edges_iter()
        return bytes(
            b"".join(
                [
                    self.links_block(islice(it, block_size))
                    for _ in range((n + block_size - 1) // block_size)
                ]
            )
        )

    def paths_block(self, names, compression_level=19):
        return bytes(b"")

    def paths_blocks(self, block_size=1024):
        """
        Compute the binary representation of the paths of the graph, one block at a time.
        Each block contains a fixed number of paths, specified by `block_size`.
        """
        n = len(self.nodes())
        self.set_segment_map(dict(zip([v for v in self.nodes()], range(1, n + 1))))
        it = self.nodes_iter()
        return bytes(
            b"".join(
                [
                    self.paths_block(islice(it, block_size))
                    for _ in range((n + block_size - 1) // block_size)
                ]
            )
        )

    def walks_block(self, names, compression_level=19):
        return bytes(b"")

    def walks_blocks(self, block_size=1024):
        """
        Compute the binary representation of the walks of the graph, one block at a time.
        Each block contains a fixed number of walks, specified by `block_size`.
        """
        n = len(self.nodes())
        self.set_segment_map(dict(zip([v for v in self.nodes()], range(1, n + 1))))
        it = self.nodes_iter()
        return bytes(
            b"".join(
                [
                    self.walks_block(islice(it, block_size))
                    for _ in range((n + block_size - 1) // block_size)
                ]
            )
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
        lines = []

        # 1. Header
        lines.append("H\tVN:Z:1.0")

        # 2. Segments (sorted by name)
        segments = []
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

        # 3. Links (sorted by From, then To)
        links = []
        for u, v, key, data in self.edges_iter(data=True, keys=True):
            if data.get("is_dovetail", False):
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
                        "is_dovetail",
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

        # 4. Paths (sorted by PathName)
        paths = []
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

        # 5. Walks (sorted by SampleID, then SeqId)
        walks = []
        for walk_id, walk_data in self.walks_iter(data=True):
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

        # 6. Containments (sorted by Container, then Contained)
        # For now, containments are not fully supported
        # This would require parsing and storing containment lines

        return "\n".join(lines)

    @classmethod
    def from_gfa(cls, filepath):  # pragma: no cover
        """Parse the given file and return a GFA object.
        Since GFA is a line-oriented format, we can parse each line separately.
        This allows to avoid keeping the entire parse tree in memory.
        """
        g = cls()

        # Load the grammar from the gfa.lark file
        grammar_file = os.path.join(
            os.path.dirname(__file__), "graph_element", "parser", "gfa.lark"
        )
        with open(grammar_file, "r") as f:
            grammar = f.read()

        # Create the parser
        parser = lark.Lark(grammar, start="start")

        # Read and parse the file line by line
        with open(filepath, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                try:
                    # Parse the line
                    tree = parser.parse(line + "\n")
                    # Process the parsed tree based on line type
                    for subtree in tree.children:
                        for child in subtree.children:
                            if child.data == "header_line":
                                # Handle header line
                                pass
                            elif child.data == "segment_line":
                                # Handle segment line
                                segment_data = {}
                                for seg_child in child.children:
                                    if seg_child.data == "segment_name":
                                        segment_data["segment_name"] = (
                                            seg_child.children[0].value
                                        )
                                    elif seg_child.data == "seq_string":
                                        segment_data["sequence"] = seg_child.children[
                                            0
                                        ].value
                                    elif seg_child.data == "optional_field":
                                        # Handle optional fields
                                        tag = seg_child.children[0].children[0].value
                                        value_type = (
                                            seg_child.children[1].children[0].value
                                        )
                                        value = seg_child.children[2].children[0].value
                                        segment_data[tag] = value

                                if (
                                    "segment_name" in segment_data
                                    and "sequence" in segment_data
                                ):
                                    g.add_node(
                                        node.Node(
                                            segment_data["segment_name"],
                                            segment_data["sequence"],
                                            len(segment_data["sequence"]),
                                            opt_fields={
                                                k: v
                                                for k, v in segment_data.items()
                                                if k not in ["segment_name", "sequence"]
                                            },
                                        )
                                    )

                            elif child.data == "link_line":
                                # Handle link line
                                link_data = {}
                                for link_child in child.children:
                                    if link_child.data == "segment_from":
                                        link_data["from_node"] = link_child.children[
                                            0
                                        ].value
                                    elif link_child.data == "orientation_from":
                                        link_data["from_orn"] = link_child.children[
                                            0
                                        ].value
                                    elif link_child.data == "segment_to":
                                        link_data["to_node"] = link_child.children[
                                            0
                                        ].value
                                    elif link_child.data == "orientation_to":
                                        link_data["to_orn"] = link_child.children[
                                            0
                                        ].value
                                    elif link_child.data == "link_overlap":
                                        link_data["alignment"] = link_child.children[
                                            0
                                        ].value
                                    elif link_child.data == "optional_field":
                                        # Handle optional fields
                                        tag = link_child.children[0].children[0].value
                                        value_type = (
                                            link_child.children[1].children[0].value
                                        )
                                        value = link_child.children[2].children[0].value
                                        link_data[tag] = value

                                if all(
                                    k in link_data
                                    for k in [
                                        "from_node",
                                        "from_orn",
                                        "to_node",
                                        "to_orn",
                                        "alignment",
                                    ]
                                ):
                                    g.add_edge(
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
                                                if k
                                                not in [
                                                    "from_node",
                                                    "from_orn",
                                                    "to_node",
                                                    "to_orn",
                                                    "alignment",
                                                ]
                                            },
                                            is_dovetail=True,
                                        )
                                    )

                            elif child.data == "containment_line":
                                # Handle containment line
                                pass

                            elif child.data == "path_line":
                                # Handle path line by adding it as a path
                                path_data = {}
                                for path_child in child.children:
                                    if path_child.data == "pathname":
                                        path_data["path_name"] = path_child.children[
                                            0
                                        ].value
                                    elif path_child.data == "segment_list":
                                        # Extract oriented segments
                                        segments = []
                                        for seg_child in path_child.children:
                                            if hasattr(seg_child, "children"):
                                                # Handle oriented_segment_sign or oriented_segment_char
                                                if len(seg_child.children) == 2:
                                                    seg_name = seg_child.children[
                                                        0
                                                    ].value
                                                    orn = seg_child.children[1].value
                                                    segments.append(f"{seg_name}{orn}")
                                        path_data["segments"] = segments
                                    elif path_child.data == "overlap_list":
                                        # Extract overlaps
                                        overlaps = []
                                        for ov_child in path_child.children:
                                            if (
                                                hasattr(ov_child, "children")
                                                and ov_child.children
                                            ):
                                                overlaps.append(
                                                    ov_child.children[0].value
                                                )
                                        path_data["overlaps"] = overlaps
                                    elif path_child.data == "optional_field":
                                        # Handle optional fields
                                        tag = path_child.children[0].children[0].value
                                        value_type = (
                                            path_child.children[1].children[0].value
                                        )
                                        value = path_child.children[2].children[0].value
                                        path_data[tag] = value

                                if "path_name" in path_data and "segments" in path_data:
                                    g.add_path(path_data)

                            elif child.data == "walk_line":
                                # Handle walk line
                                walk_data = {}
                                for walk_child in child.children:
                                    if walk_child.data == "sample_id":
                                        walk_data["sample_id"] = walk_child.children[
                                            0
                                        ].value
                                    elif walk_child.data == "hapindex":
                                        walk_data["hapindex"] = int(
                                            walk_child.children[0].value
                                        )
                                    elif walk_child.data == "seq_id":
                                        walk_data["seq_id"] = walk_child.children[
                                            0
                                        ].value
                                    elif walk_child.data == "seq_start":
                                        value = walk_child.children[0].value
                                        walk_data["seq_start"] = (
                                            None if value == "*" else int(value)
                                        )
                                    elif walk_child.data == "seq_end":
                                        value = walk_child.children[0].value
                                        walk_data["seq_end"] = (
                                            None if value == "*" else int(value)
                                        )
                                    elif walk_child.data == "walk":
                                        walk_data["walk"] = walk_child.children[0].value
                                    elif walk_child.data == "optional_field":
                                        # Handle optional fields
                                        tag = walk_child.children[0].children[0].value
                                        value_type = (
                                            walk_child.children[1].children[0].value
                                        )
                                        value = walk_child.children[2].children[0].value
                                        walk_data[tag] = value

                                if "sample_id" in walk_data and "walk" in walk_data:
                                    g.add_walk(walk_data)

                            elif child.data == "jump_line":
                                # Handle jump line
                                pass

                except lark.exceptions.LarkError as e:
                    # Skip lines that don't parse correctly
                    logger.warning(f"Failed to parse line {i+1}: {line_[:50]}{'...' if len(line_) > 50 else ''} - {e}")
                    continue

        return g

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
                # Get segment name if available
                print(f"  Node: {node_id}")
                for key, value in data.items():
                    if key not in ["nid", "sequence", "slen"]:
                        print(f"    {key}: {value}")
                if "sequence" in data:
                    print(f"    sequence: {data['sequence']}")
                if "slen" in data:
                    print(f"    length: {data['slen']}")
            print()

        # Print edges
        if self.edges():
            print("--- Edges ---")
            for u, v, key, data in self.edges_iter(data=True, keys=True):
                print(f"  Edge: {key} ({u} -> {v})")
                for attr, val in data.items():
                    if attr not in ["from_node", "to_node", "eid"]:
                        print(f"    {attr}: {val}")
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

    def __eq__(self, other):
        """
        :TODO:
            * make a lut for subgraphs (try to think for a way to write
              _make_edge_lut in a reusable way...
        """
        try:
            # Nodes must be defined, so there is no reason to
            # create a LUT
            for nid, node_ in self.nodes_iter(data=True):
                if node_ != other.nodes(identifier=nid):
                    return False

            self_edge_table = self._make_edge_table()
            other_edge_table = other._make_edge_table()
            self_lut, self_edge_virtuals = self._make_edge_lut()
            other_lut, other_edge_virtuals = other._make_edge_lut()
            for alias, list_ids in self_lut.items():
                while len(list_ids):
                    id_ = list_ids.pop()
                    found = False
                    index = 0
                    edge_ = self._look_for_edge(id_, self_edge_table)
                    while not found and index < len(other_lut[alias]):
                        other_id = other_lut[alias][index]
                        if edge_ == other._look_for_edge(other_id, other_edge_table):
                            found = True
                        else:
                            index += 1
                    if not found:
                        return False
                    # if is found remove it from list
                    # to speed up next searches.
                    other_lut[alias].pop(index)
                # if other_lut has other ids attached to that alias, then
                # graphs are not equals
                # if not len(other_lut[alias]):
                #    return False

            for edge_ in self_edge_virtuals:
                found, index = _index(edge_, other_edge_virtuals)
                if not found:
                    return False
                other_edge_virtuals.pop(index)

            # I think it's difficult to have lots of subgraphs
            # If I am wrong a subgraphs lut will be made and the comparison
            # should be nearly linear in time
            self_subgraphs = [sub.as_dict() for sub in self.subgraphs().values()]
            other_subgraphs = [sub.as_dict() for sub in other.subgraphs().values()]
            for sub_ in self_subgraphs:
                found, index = _index(sub_, other_subgraphs)
                if not found:
                    return False
                other_subgraphs.pop(index)

            # Compare paths
            self_paths = [path for path in self.paths().values()]
            other_paths = [path for path in other.paths().values()]
            for path_ in self_paths:
                found, index = _index(path_, other_paths)
                if not found:
                    return False
                other_paths.pop(index)

            # Compare walks
            self_walks = [walk for walk in self.walks().values()]
            other_walks = [walk for walk in other.walks().values()]
            for walk_ in self_walks:
                found, index = _index(walk_, other_walks)
                if not found:
                    return False
                other_walks.pop(index)

        except (AttributeError, KeyError) as e:
            return False
        return True

    def __neq__(self, other):
        return not self == other

    def compression(self, type_compression="by_nodes"):
        if type_compression == "by_edges":
            compression_graph_by_edges(self)
        else:
            count_edge_compacted = compression_graph_by_nodes(self)
            while not count_edge_compacted == 0:
                count_edge_compacted = compression_graph_by_nodes(self)

    def overlap_consistency(self, external_file=None):
        FOLDER, _ = os.path.split(__file__)
        return check_overlap(self, FOLDER.rstrip("pygfa"), external_file)

    def subgraphs_extractor(self, n_source, distance):
        extract_subgraph(self, n_source, distance)

    def to_bgfa(
        self,
        block_size: int = 1024,
        compression_method: str = "zstd",
        compression_level: int = 19,
    ) -> bytes:
        """Convert this GFA graph to BGFA binary format.

        :param block_size: Block size for BGFA format (default: 1024)
        :param compression_method: Compression method for string data (default: "zstd")
        :param compression_level: Compression level (default: 19)
        :return: BGFA binary data
        """
        from pygfa.bgfa import BGFAWriter

        writer = BGFAWriter(self, block_size=block_size, compression_options={})
        return writer.to_bgfa()

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
        # Simple logging without setting up handlers (handled in bgfa.py)
        if verbose or debug:
            import logging

            logger = logging.getLogger(__name__)
            logger.info(f"GFA.from_bgfa(): Starting to read BGFA file: {file_path}")

        from pygfa.bgfa import read_bgfa

        return read_bgfa(file_path, verbose=verbose, debug=debug, logfile=logfile)

    def to_bgfa(
        self,
        file=None,
        block_size=1024,
        compression_options=None,
        verbose: bool = False,
        debug: bool = False,
        logfile: str = None,
    ) -> bytes:
        """Convert this GFA graph to BGFA binary format and write to file.

        :param file: Output file path or file object (optional)
        :param block_size: Block size for BGFA format
        :param compression_options: Dictionary of compression options
        :param verbose: If True, log detailed information
        :param debug: If True, log debug information
        :param logfile: Path to log file (if None and verbose=True, uses a temporary file)
        :return: BGFA binary data if file is None, otherwise writes to file
        """
        # Simple logging without setting up handlers (handled in bgfa.py)
        if verbose or debug:
            import logging

            logger = logging.getLogger(__name__)
            output_file = file if file else "bytes"
            logger.info(
                f"GFA.to_bgfa(): Starting conversion to BGFA, output: {output_file}"
            )

        from pygfa.bgfa import to_bgfa as bgfa_to_bgfa

        if compression_options is None:
            compression_options = {}

        # Extract all the compression strategy parameters from the dictionary
        # with default values
        segment_names_header = compression_options.get("segment_names_header", None)
        segment_names_payload_lengths = compression_options.get(
            "segment_names_payload_lengths", None
        )
        segment_names_payload_names = compression_options.get(
            "segment_names_payload_names", None
        )
        segments_header = compression_options.get("segments_header", None)
        segments_payload_lengths = compression_options.get(
            "segments_payload_lengths", None
        )
        segments_payload_strings = compression_options.get(
            "segments_payload_strings", None
        )
        links_header = compression_options.get("links_header", None)
        links_payload_from = compression_options.get("links_payload_from", None)
        links_payload_to = compression_options.get("links_payload_to", None)
        links_payload_cigar_lengths = compression_options.get(
            "links_payload_cigar_lengths", None
        )
        links_payload_cigar = compression_options.get("links_payload_cigar", None)
        paths_header = compression_options.get("paths_header", None)
        paths_payload_names = compression_options.get("paths_payload_names", None)
        paths_payload_segment_lengths = compression_options.get(
            "paths_payload_segment_lengths", None
        )
        paths_payload_path_ids = compression_options.get("paths_payload_path_ids", None)
        paths_payload_cigar_lengths = compression_options.get(
            "paths_payload_cigar_lengths", None
        )
        paths_payload_cigar = compression_options.get("paths_payload_cigar", None)
        walks_header = compression_options.get("walks_header", None)
        walks_payload_sample_ids = compression_options.get(
            "walks_payload_sample_ids", None
        )
        walks_payload_hep_indices = compression_options.get(
            "walks_payload_hep_indices", None
        )
        walks_payload_sequence_ids = compression_options.get(
            "walks_payload_sequence_ids", None
        )
        walks_payload_start = compression_options.get("walks_payload_start", None)
        walks_payload_end = compression_options.get("walks_payload_end", None)
        walks_payload_walks = compression_options.get("walks_payload_walks", None)

        return bgfa_to_bgfa(
            self,
            file=file,
            block_size=block_size,
            segment_names_header_compression_strategy=segment_names_header,
            segment_names_payload_lengths_compression_strategy=segment_names_payload_lengths,
            segment_names_payload_names_compression_strategy=segment_names_payload_names,
            segments_header_compression_strategy=segments_header,
            segments_payload_lengths_compression_strategy=segments_payload_lengths,
            segments_payload_strings_compression_strategy=segments_payload_strings,
            links_header_compression_strategy=links_header,
            links_payload_from_compression_strategy=links_payload_from,
            links_payload_to_compression_strategy=links_payload_to,
            links_payload_cigar_lengths_compression_strategy=links_payload_cigar_lengths,
            links_payload_cigar_compression_strategy=links_payload_cigar,
            paths_header_compression_strategy=paths_header,
            paths_payload_names_compression_strategy=paths_payload_names,
            paths_payload_segment_lengths_compression_strategy=paths_payload_segment_lengths,
            paths_payload_path_ids_compression_strategy=paths_payload_path_ids,
            paths_payload_cigar_lengths_compression_strategy=paths_payload_cigar_lengths,
            paths_payload_cigar_compression_strategy=paths_payload_cigar,
            walks_header_compression_strategy=walks_header,
            walks_payload_sample_ids_compression_strategy=walks_payload_sample_ids,
            walks_payload_hep_indices_compression_strategy=walks_payload_hep_indices,
            walks_payload_sequence_ids_compression_strategy=walks_payload_sequence_ids,
            walks_payload_start_compression_strategy=walks_payload_start,
            walks_payload_end_compression_strategy=walks_payload_end,
            walks_payload_walks_compression_strategy=walks_payload_walks,
            verbose=verbose,
            debug=debug,
            logfile=logfile,
        )


if __name__ == "__main__":  # pragma: no cover
    pass
