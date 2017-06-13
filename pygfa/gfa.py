import sys
import re
from parser.lines import header, segment, link, containment, path
from parser.lines import edge, gap, fragment, group
from graph_element import node, edge as ge
import networkx as nx

class GFA (nx.MultiGraph):
    """GFA will use a networkx MultiGraph as structure to contain the elements
    of the specification. GFA graphs accept only instances coming from
    the graph_elements package."""

    def __init__ (self):
        # a virtual id assigned to edges (graph edges) that don't have an id.
        # Their id will be virtual_# where # will be given by next_virtual_id.
        self.next_virtual_id = 0;
        self._graph = nx.MultiGraph ()

    # Simulate networkx graph behaviour with composition.
    def nodes (self, **kwargs):
        return self._graph.nodes (**kwargs)

    def edges (self, **kwargs):
        return self._graph.edges (**kwargs)

    @property
    def node (self):
        return self._graph.node

    @property
    def edge (self):
        return self._graph.edge

    def clear (self):
        """Call networkx 'clear' method and reset the virtual id counter."""
        self._graph.clear ()
        self.next_virtual_id = 0
           
    def add_node (self, new_node):
        """Add a graph_element Node to the GFA graph using the node id as key,
        its sequence and sequence length will be individual attribute on the graph and
        all the remained optional field will be stored on a single list as a node attributes
        'opt_fields'."""
        if not node.is_node (new_node):
            raise node.InvalidNodeError ("The object given is not a node.")

        self._graph.add_node (\
                                  new_node.nid, id=new_node.nid, sequence=new_node.sequence, \
                                  slen=new_node.slen, opt_fields=new_node.opt_fields)
        return True
        

    def add_edge (self, new_edge):
        """Add a graph_element Edge to the GFA graph using  the edge id as key, if its
        id is '*' or None the edge will be given a virtual_id, in either case the original
        edge id will be preserved as edge attribute. All edge attributes will be stored as
        netwrorkx edge attributes and its optfields will be store as a separate list in the edge
        within the attribute 'opt_fields'."""
        print (ge.is_edge (new_edge))
        if not ge.is_edge (new_edge):
            raise ge.InvalidEdgeError ("The object given is not an Edge.")

        # this approach is not so good, the id regexp allows to have a + or -
        # so this way we could cut off a part of the id and to the orientation
        from_node = new_edge.from_node
        if from_node[-1] in ('+', '-'):
            from_node = from_node[0:-1]

        to_node = new_edge.to_node
        if to_node[-1] in ('+', '-'):
            to_node = to_node[0:-1]

        key = new_edge.eid
        if new_edge.eid == None or new_edge.eid == '*':
            key = "virtual_{0}".format (self.next_virtual_id)
            self.next_virtual_id += 1
        
        self._graph.add_edge ( \
                                   from_node, to_node, key, \
                                   id=new_edge.eid, \
                                   from_node = new_edge.from_node, \
                                   to_node = new_edge.to_node, \
                                   from_positions = new_edge.from_positions, \
                                   to_positions = new_edge.to_positions, \
                                   alignment = new_edge.alignment, \
                                   displacement = new_edge.displacement ,\
                                   variance = new_edge.variance, \
                                   opt_fields = new_edge.opt_fields \
                                   )
        return True
