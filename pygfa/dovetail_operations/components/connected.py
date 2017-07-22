"""
Algorithms to find connected components in the graph considering
only dovetails overlaps.

Adapted using the networkx connected module:
networkx/networkx/algorithms/components/connected.py
"""

def _plain_bfs_dovetails(gfa_, source):
    if source not in gfa_:
        return ()
    seen = set()
    nextlevel = {source}
    while nextlevel:
        thislevel = nextlevel
        nextlevel = set()
        for v in thislevel:
            if v not in seen:
                yield v
                seen.add(v)
                nextlevel.update(gfa_.right(v))
                nextlevel.update(gfa_.left(v))

def dovetails_nodes_connected_component(gfa_, source):
    return set(_plain_bfs_dovetails(gfa_, source))

def dovetails_nodes_connected_components(gfa_, with_sequence=True):
    """Compute the connected components in the GFA graph.

    :param with_sequence: If set start the computation considering
        only nodes where the 'sequence' propery is present. Consider
        every nodes in the graph otherwise.
    """
    seen = set()
    nodes = gfa_.nodes(with_sequence=with_sequence)
    for v in nodes:
        if v not in seen:
            c = set(_plain_bfs_dovetails(gfa_, v))
            yield c
            seen.update(c)

def dovetails_connected_components_subgraphs(\
                                            gfa_, \
                                            copy=True, \
                                            with_sequence=True):
    """Generate connected components as subgraphs.

    :return comp: A generator of graphs, one for each connected
    component of gfa_.
    """
    for c in dovetails_nodes_connected_components(gfa_, \
                                                with_sequence=with_sequence):
        if copy:
            yield gfa_.dovetails_subgraph(c).copy()
        else:
            yield gfa_.dovetails_subgraph(c)
