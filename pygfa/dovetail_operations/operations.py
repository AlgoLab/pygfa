from pygfa.dovetail_operations.components.connected import dovetails_nodes_connected_components

def dovetails_remove_small_components(self, min_length):
    """Remove all the connected components where
    the sequences length is less than min_length.
    
    Find all the connected components nodes,
    for each component obtain the sum of the
    sequences length.
    If length is less than the given length remove the connected
    component nodes.

    :param min_length: An integer describing the required length
        to keep a connected component.

    :note:
       When connected components are computed only dovetail overlaps
      edges are considered.
    """
    conn_components = dovetails_nodes_connected_components(self)
    for conn_comp in conn_components:
        length = 0
        for nid in conn_comp:
            node_ = self.node(nid)
            try:
                length += node_['slen']
            except (TypeError, KeyError):
                pass
        if length < min_length:
            for nid in conn_comp:
                self.remove_node(nid)
