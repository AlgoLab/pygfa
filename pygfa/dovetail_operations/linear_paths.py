"""
Module that contain operation to find linearh paths
in a GFA graph.
"""

from pygfa.dovetail_operations.components.connected import dovetails_nodes_connected_components as connected_components
from pygfa.dovetail_operations.components.connected import dovetails_nodes_connected_component as connected_component

def _path_endpoints(gfa_, components=False):
    """Find all nodes whose right degree or left degree is != 1

    :param components (False, nid): If set to False compute all paths enpoints
        in the graph. If a node id is given, compute the endpoints only on the
        connected component where the node id belongs.
    """
    if components is not False:
        ccs = iter([connected_component(gfa_, components)])
    else:
        ccs = connected_components(gfa_)

    seen = set()
    for cc in ccs:
        for node_ in cc:
            if node_ not in seen:
                if gfa_.right_degree(node_) != 1 \
                  or gfa_.left_degree(node_) != 1:
                    seen.add(node_)
                    yield node_

def linear_path(gfa_, node_, keys=False):
    """Return the oriented edges involved in a linear path
    where that contain the given node.
    """
    return gfa_.dovetails_linear_path_iter(node_, keys=keys)

def linear_paths(gfa_, components=False, keys=False):
    for ep in _path_endpoints(gfa_, components=components):
        for n in gfa_.dovetails_neighbors(ep):
            lin_path = list(linear_path(gfa_, n, keys=keys))
            if len(lin_path) > 0:
                yield lin_path
