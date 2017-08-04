from networkx.algorithms.components.connected import node_connected_component as nx_node_connected_component
from networkx.algorithms.components.connected import connected_components as nx_connected_components

from pygfa.dovetail_operations.operations import *
from pygfa.dovetail_operations.components.connected import *
from pygfa.dovetail_operations.components.biconnected import *
from pygfa.dovetail_operations.linear_paths import *
from pygfa.dovetail_operations.simple_paths import *

import pygfa.gfa

def node_connected_component(gfa_, nid):
    """Return a the connected component
    belonging to the given node.

    :param nid: The id of the node to find the reachable nodes.
    """
    if nid not in gfa_:
        raise pygfa.gfa.GFAError("The source node is not in the graph.")
    return nx_node_connected_component(\
                        gfa_._graph, nid)

def nodes_connected_components(gfa_):
    """Return a generator of sets with nodes of each weakly
    connected component in the graph.
    """
    return nx_connected_components(gfa_._graph)

def remove_dead_ends(\
                      gfa_, \
                      min_length, \
                      consider_sequence=False, \
                      safe_remove=False):
    """Remove all the nodes where its right
    degree and its left degree are the following (0,0), (1,0), (1,0)
    and the length of the sequence is less than the given length.

    :param min_length:
    :param consider_sequence: If set try to get the sequence length
        where length field is not defined.
    :param safe_remove: If set the operation doesn't remove nodes
        where is not possible to obtain the length value.

    :note:
        Using the right and left degree, only dovetails overlaps
        are considered.
    """
    to_remove = set()
    for nid, node_ in gfa_.nodes_iter(data=True):
        left_deg = gfa_.left_degree(nid)
        right_deg = gfa_.right_degree(nid)
        if (left_deg, right_deg) in [(0,0), (0,1), (1,0)]:
            try:
                length = node_['slen']
                if length is None:
                    if consider_sequence:
                        length = len(node_['sequence']) \
                          if node_['sequence'] != "*" else 0
                    else:
                        length = 0
                if length < min_length:
                    to_remove.add(nid)
            except KeyError:
                if not safe_remove:
                    to_remove.add(nid)

    for nid in to_remove:
        gfa_.remove_node(nid)
