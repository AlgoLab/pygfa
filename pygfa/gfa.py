from parser.lines import header, segment, link, containment, path
from parser.lines import edge, gap, fragment, group
from parser import line
from graph_element import node, edge as ge, subgraph as sg
import copy
import networkx as nx

class InvalidSearchParameters (Exception): pass
class InvalidElementError (Exception): pass

class GFA ():
    """GFA will use a networkx MultiGraph as structure to contain the elements
    of the specification. GFA graphs accept only instances coming from
    the graph_elements package."""

    def __init__ (self):
        # a virtual id assigned to edges (graph edges) that don't have an id.
        # Their id will be 'virtual_#' where # will be given by next_virtual_id.
        self._next_virtual_id = 0;
        self._graph = nx.MultiDiGraph ()
        self._subgraphs = {}

    # Simulate networkx graph behaviour with composition.
    def nodes (self, **kwargs):
        """Return a copy list of all the nodes in the graph."""
        return self._graph.nodes (**kwargs)

    def edges (self, **kwargs):
        """Return a copy list of all the edges in the graph."""
        return self._graph.edges (**kwargs)

    @property
    def subgraphs (self):
        return self._subgraphs

    # removed the property accessor to make it coherent with the edge accessor
    def node (self, identifier=None):
        """An interface to access the node method of the netwrokx graph."""
        if identifier == None:
            return self._graph.node
        else:
            return self._graph.node[identifier]
        
    def edge (self, identifier=None):
        """An interface to the edge method present in networkx.
        It's different from the networkx accessor in that it's not a property, so empty brackets
        are needed to call the networkx edge property.
        """
        if identifier == None:
            return self._graph.edge
        if isinstance (identifier, tuple) and len (identifier) >= 2:
            return self.search_edge_by_nodes (identifier)
        else:
            return self.search_edge_by_key (identifier)

    def get (self, key):
        """Return the element pointed by the specified key."""
        try:
            if key in self._graph.node:
                return self.node(key)

            if key in self._subgraphs:
                return self._subgraphs[key]
            
            edge = self.search_edge_by_key (key)
            if edge != None:
                return edge
        except:
            None


    def as_graph_element (self, key):
        """Given a key of an existing node, edge or subgraph, return its equivalent
        graph element object."""
        element = self.get (key)
        if element == None:
            raise InvalidElementError ("No graph element has the given key.")

        tmp_list = copy.deepcopy (element)
        if isinstance (element, sg.Subgraph):
            return copy.deepcopy (element)
        if 'nid' in element:
            tmp_list.pop ('nid')
            tmp_list.pop ('sequence')
            tmp_list.pop ('slen')
            return node.Node (element['nid'], element['sequence'], element['slen'], opt_fields=tmp_list)
        if 'eid' in element:
            tmp_list.pop ('eid')
            tmp_list.pop ('from_node')
            tmp_list.pop ('to_node')
            tmp_list.pop ('from_positions')
            tmp_list.pop ('to_positions')
            tmp_list.pop ('alignment')
            tmp_list.pop ('variance')
            tmp_list.pop ('displacement')
            return ge.Edge (\
                                element['eid'], element['from_node'], element['to_node'], \
                                element['from_positions'], element['to_positions'], \
                                element['alignment'], element['displacement'], \
                                element['variance'], \
                                opt_fields=tmp_list\
                            )
        
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
        """Call networkx 'clear' method, reset the virtual id counter and
        delete all the subgraphs."""
        self._graph.clear ()
        self._next_virtual_id = 0
        self._subgraphs = {}

        
    def add_graph_element (self, element):
        """Add a graph element (Node, Edge or Subgraph) to the graph."""
        if isinstance (element, node.Node):
            self.add_node (element)
        elif isinstance (element, ge.Edge):
            self.add_edge (element)
        elif isinstance (element, sg.Subgraph):
            self.add_subgraph (element)
           
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
        """Add a graph_element Edge or a networkx edge to the GFA graph using  the edge id as key, if its
        id is '*' or None the edge will be given a virtual_id, in either case the original
        edge id will be preserved as edge attribute. All edge attributes will be stored as
        netwrorkx edge attributes and its optfields will be store as a separate list in the edge
        within the attribute 'opt_fields'."""
        if not ge.is_edge (new_edge):
            raise ge.InvalidEdgeError ("The object is not a valid edge.")

        # TODO: check that it's not possible not to have a reference at this point
        # making the next comment not problematic.
        
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
            key = "virtual_{0}".format (self._get_virtual_id ())
        
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


    def add_subgraph (self, subgraph):
        if not isinstance (subgraph, sg.Subgraph):
            raise sg.InvalidSubgraphError ("The object given is not a subgraph.")

        key = subgraph.sub_id
        if key == '*':
            key = "virtual_{0}".format (self._get_virtual_id ())
        
        self._subgraphs[key] = copy.deepcopy (subgraph)


    def _get_virtual_id (self):
        key = self._next_virtual_id
        self._next_virtual_id += 1
        return key

    def get_subgraph (self, sub_key):
        """Returns a new GFA graph structure with the nodes, edges and subgraphs
        specified in the elements attributes of the subgraph object pointed by the id.
        Return None if the subgraph id doesn't exist."""
        if not sub_key in self._subgraphs:
            raise InvalidSubgraphError ("There is no subgraph pointed by this key.")

        subgraph = self._subgraphs[sub_key]
        subGFA = GFA()

        for element in subgraph.elements:
            # creating a new GFA graph and the add method, the virtual id are recomputed
            if element[-1] in ('+', '-'):
                element = element[0:-1]
                
            subGFA.add_graph_element (self.as_graph_element (element))

        return subGFA
            

    def pprint (self):
        """A basic pretty print function for nodes and edges."""
        string = "\nGRAPH:\nNodes: [\n"
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

        string += "\nSubgraphs: [\n"    
        for key, datas in self.subgraphs.items ():
            string += str (key) + "\t: {sub_id:" + str (datas.sub_id) + "\t elements:" + str.join (", ", datas.elements) + "}\n"
        string += "]\n"
        return string


