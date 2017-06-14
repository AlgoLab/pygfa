from parser.lines import header, segment, link, containment, path
from parser.lines import edge, gap, fragment, group
from parser import line
from graph_element import node, edge as ge
import copy
import networkx as nx

class InvalidSearchParameters (Exception): pass

class GFA (nx.MultiGraph):
    """GFA will use a networkx MultiGraph as structure to contain the elements
    of the specification. GFA graphs accept only instances coming from
    the graph_elements package."""

    def __init__ (self):
        # a virtual id assigned to edges (graph edges) that don't have an id.
        # Their id will be 'virtual_#' where # will be given by next_virtual_id.
        self.next_virtual_id = 0;
        self._graph = nx.MultiGraph ()

    # Simulate networkx graph behaviour with composition.
    def nodes (self, **kwargs):
        """Return a copy list of all the nodes in the graph."""
        return copy.deepcopy (self._graph.nodes (**kwargs))

    def edges (self, **kwargs):
        """Return a copy list of all the edges in the graph."""
        return copy.deepcopy (self._graph.edges (**kwargs))

#    @property
#    def node (self):
#        return self._graph.node

#    @property
#    def edge (self):
#        return self._graph.edge

    # TODO:
    # If this modifications are accepted we could
    # change the name of get_node and get_edge to node and
    # edge like above
    def get_node (self, node_id='*'):
        if node_id == '*':
            return self._graph.node
        if node_id in self._graph.node:
            return self._graph.node[node_id]
        return None

    def get_edges (self, **kwargs):
        return selg._graph.edges (**kwargs)
    
    def get_edge (self, identifier='*'):
        """An interface to the edge method present in networkx.
        If '*' is given returns all the individual edges in the graph.
        """
        if identifier == '*':
            return self._graph.edge
        if isinstance (identifier, tuple) and len (identifier) >= 2:
            return self.search_edge_by_nodes (identifier)
        else:
            return self.search_edge_by_key (identifier)

        
    def search_edge_by_key (self, key):
        for from_node, to_node, edge_key in self._graph.edges_iter (keys=True):
            if key == edge_key:
                return self._graph.edge[from_node][to_node][edge_key]
        return None

    def search_edge_by_nodes (self, nodes):
        """If given a tuple with from_node and to_node return all the edges
        between the two nodes.
        If a third element is present in the tuple it return the exact edge between
        the two nodes with the key specified by the third element.
        If no match is found return None."""
        if len (nodes) < 2:
            raise InvalidSearchParameters ()
        from_node = nodes [0]
        to_node = nodes [1]

        try:
            if len (nodes) > 2:
                key = nodes[2]
                return self._graph.edge[from_node][to_node][key]
            
            return self._graph.edge[from_node][to_node]
        except:
            return None



    def clear (self):
        """Call networkx 'clear' method and reset the virtual id counter."""
        self._graph.clear ()
        self.next_virtual_id = 0

    def add (self, element):
        if isinstance (element, node.Node):
            self.add_node (element)
        elif isinstance (element, ge.Edge):
            self.add_edge (element)
           
    def add_node (self, new_node):
        """Add a graph_element Node to the GFA graph using the node id as key,
        its sequence and sequence length will be individual attribute on the graph and
        all the remained optional field will be stored on a single list as a node attributes
        'opt_fields'."""
        if not node.is_node (new_node):
            raise node.InvalidNodeError ("The object given is not a node.")

        self._graph.add_node (\
                                  new_node.nid, nid=new_node.nid, sequence=new_node.sequence, \
                                  slen=new_node.slen, **new_node.opt_fields)
        return True
        

    def add_edge (self, new_edge):
        """Add a graph_element Edge to the GFA graph using  the edge id as key, if its
        id is '*' or None the edge will be given a virtual_id, in either case the original
        edge id will be preserved as edge attribute. All edge attributes will be stored as
        netwrorkx edge attributes and its optfields will be store as a separate list in the edge
        within the attribute 'opt_fields'."""
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
                                   from_node, to_node, key=key, \
                                   eid=new_edge.eid, \
                                   from_node = new_edge.from_node, \
                                   to_node = new_edge.to_node, \
                                   from_positions = new_edge.from_positions, \
                                   to_positions = new_edge.to_positions, \
                                   alignment = new_edge.alignment, \
                                   displacement = new_edge.displacement ,\
                                   variance = new_edge.variance, \
                                   **new_edge.opt_fields \
                                   )
        return True


    def pprint (self):
        """A basic pretty print function for nodes and edges."""
        string = "\nNodes: [\n"
        for node, datas in self._graph.nodes_iter (data=True):
            string += str (node) + "\t: {"
            for name, data in datas.items():
                string += str(name) + ": " + str (data) + "\t"
            string += "}\n"
        string += "]\n"

        string += "\nEdges: [\n"    
        for from_node, to_node, key, datas in self._graph.edges_iter (keys=True, data=True):
            string += str (key) + "\t: {"
            for name, data in datas.items():
                string += str(name) + ": " + str (data) + "\t"
            string += "}\n"
        string += "]\n"
        return string

