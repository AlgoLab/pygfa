"""
Iterators used by the GFA graph.
This iterators work considering only edges
representing dovetails overlaps.
"""

# Note that self will be referred to the GFA class, keep this in mind
# while reading this class.

class Iterator:
    def dovetails_iter(self, nbunch=None, keys=False, data=False):
        """Return an iterator on edges that describe
        dovetail overlaps with the given node."""
        for from_node, to_node, key, edge_ in self._graph.edges_iter(nbunch, keys=True, data=True):
            if edge_['is_dovetail']:
                if data is True:
                    yield (from_node, to_node, key, edge_) if keys \
                      else (from_node, to_node, edge_)
                else:
                    yield (from_node, to_node, key) if keys \
                      else (from_node, to_node)

    def dovetails_nbunch_iter(self, nbunch=None):
        dovetails_nodes = set()
        for from_, to_ in self.dovetails_iter():
            dovetails_nodes.add(from_)
            dovetails_nodes.add(to_)
        if nbunch is None:
            bunch = iter(dovetails_nodes)
        elif nbunch in dovetails_nodes:
            bunch = iter([nbunch])
        else:
            def bunch_iter(nlist, adj):
                try:
                    for n in nlist:
                        if n in adj:
                            yield n
                except TypeError as e:
                    message = e.args[0]
                    # capture error for non-sequence/iterator nbunch.
                    if 'iter' in message:
                        raise NetworkXError(
                            "nbunch is not a node or a sequence of nodes.")
                    # capture error for unhashable node.
                    elif 'hashable' in message:
                        raise NetworkXError(
                            "Node %s in the sequence nbunch is not a valid node."%n)
                    else:
                        raise
            bunch = bunch_iter(nbunch, dovetails_nodes)
        return bunch
            

    def dovetails_neighbors_iter(self, nid, keys=False, data=False):
        for from_node, to_node, key, edge_ in self.dovetails_iter(nid, keys=True, data=True):
            if data is True:
                yield (from_node, to_node, key, edge_) if keys \
                  else (from_node, to_node, edge_)
            else:
                yield (from_node, to_node, key) if keys \
                  else (from_node, to_node)

    def right_end_iter(self, nbunch, keys=False, data=False):
        """Return an iterator over dovetail edges where
        nodes id  right-segment end is taken into account
        in the overlap
        """
        try:
            if isinstance(nbunch, str):
                raise TypeError
            nids = set(nbunch)
        except TypeError:
            nids = set()
            nids.add(nbunch)

        for nid in nids:
            for from_node, to_node, key, edge_ in self.dovetails_neighbors_iter(nid, keys=True, data=True):

                if nid == edge_["from_node"] \
                  and edge_["from_segment_end"] == "R":
                    if data is True:
                        yield (from_node, to_node, key, edge_) if keys \
                          else (from_node, to_node, edge_)
                    else:
                        yield (from_node, to_node, key) if keys \
                          else (from_node, to_node)

                if nid == edge_["to_node"] \
                  and edge_["to_segment_end"] == "R":
                    if data is True:
                        yield (from_node, to_node, key, edge_) if keys \
                          else (from_node, to_node, edge_)
                    else:
                        yield (from_node, to_node, key) if keys \
                          else (from_node, to_node)

    def right(self, nid):
        """Return all the nodes connected to the right
        end of the given node sequence.
        """
        return list(to_ for from_, to_ in self.right_end_iter(nid))

    def left_end_iter(self, nbunch, keys=False, data=False):
        """Return an iterator over dovetail edges where
        left segment-end of the nodes ids given are taken into account
        in the overlap
        """
        try:
            if isinstance(nbunch, str):
                raise TypeError
            nids = set(nbunch)
        except TypeError:
            nids = set()
            nids.add(nbunch)

        for nid in nids:
            for from_node, to_node, key, edge_ in self.dovetails_neighbors_iter(nid, keys=True, data=True):

                if nid == edge_["from_node"] \
                  and edge_["from_segment_end"] == "L":
                    if data is True:
                        yield (from_node, to_node, key, edge_) if keys \
                          else (from_node, to_node, edge_)
                    else:
                        yield (from_node, to_node, key) if keys \
                          else (from_node, to_node)

                if nid == edge_["to_node"] \
                  and edge_["to_segment_end"] == "L":
                    if data is True:
                        yield (from_node, to_node, key, edge_) if keys \
                          else (from_node, to_node, edge_)
                    else:
                        yield (from_node, to_node, key) if keys \
                          else (from_node, to_node)

    def left(self, nid):
        """Return all the nodes connected to the left
        end of the given node sequence.
        """
        return list(to_ for from_, to_ in self.left_end_iter(nid))

