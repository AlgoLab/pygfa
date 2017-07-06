"""

GFA representation trough a networkx MulitDiGraph.

"""

import copy
import re
import logging

import networkx as nx

from pygfa.graph_element.parser import header, segment, link, containment, path
from pygfa.graph_element.parser import edge, gap, fragment, group
from pygfa.graph_element import node, edge as ge, subgraph as sg
from pygfa import gfa1_serializer as gs1, gfa2_serializer as gs2


gfa_logger = logging.getLogger(__name__)


class InvalidSearchParameters(Exception): pass
class InvalidElementError(Exception): pass
class GFAError(Exception): pass


class Element:
    """Represent the types of graph a GFA grapg object can have.
    """
    NODE = 0
    EDGE = 1
    SUBGRAPH = 2

def VALUE_EQUALITY_COMPARATOR(obj, value):
    """
    A standard comparator to get the value from the majority of the graph
    elements present in the GFA graph, if a line.field is found then its
    value is taken into account.
    """
    if line.is_field(obj):
        return obj.value == value
    else:
        return obj == value

def IGNORE_VALUE_COMPARATOR(obj, value):
    return True
    
class GFA():
    """
    GFA will use a networkx MultiDiGraph as structure to contain
    the elements of the specification.
    GFA graphs directly accept only instances coming from the
    graph_elements package, but can contains any kind of data
    undirectly by accessing the `_graph` attribute.
    """

    def __init__(self, base_graph=None):
        """Creates a GFA graph.

        If :param base_graph: is not `None` use the graph provided
        as base for the graph.

        A **virtual id** is assigned to edges(graph edges) that don't
        have an id.
        Their id will be **'virtual_#'** where **#** will be given
        by `next_virtual_id`.

        :param base graph: An instance of a networkx.DiGraph or its
        derivative classes.
        """
        if base_graph != None and not isinstance(base_graph, nx.DiGraph):
            raise GFAError("{0} cannot be used as base graph, ".format(type(base_graph)) + \
                                "use networkx.DiGraph or networkx.MultiDiGraph instead.")
        
        self._graph = nx.MultiDiGraph(base_graph)
        self._subgraphs = {}
        self._next_virtual_id = 0 if base_graph == None else \
                                self._find_max_virtual_id();

    def _get_virtual_id(self, increment=True):
        key = self._next_virtual_id
        if increment == True:
            self._next_virtual_id += 1
        return key

    def _find_max_virtual_id(self):
        # nodes cannot have a virtual_id, so don't search inside them
        virtual_rxp = "^virtual_([\d]+)$"
        regexp = re.compile(virtual_rxp)
        virtual_keys = [0]
        
        for u,v, key in self._graph.edges_iter(keys=True):
            match = regexp.fullmatch(key)
            if match:
                virtual_keys.append(int(match.group(1)))

        for key, data in self._subgraphs.items():
            match = regexp.fullmatch(key)
            if match:
                virtual_keys.append(int(match.group(1)))

        return max(virtual_keys)
            
    # Simulate networkx graph behaviour with composition.
    def nodes(self, **kwargs):
        """Return all the nodes in the graph."""
        return self._graph.nodes(**kwargs)

    def edges(self, **kwargs):
        """Return all the edges in the graph."""
        return self._graph.edges(**kwargs)

    def subgraphs(self, identifier=None):
        """An interface to access to the subgraphs inside
        the GFA object.
        """
        if identifier == None:
            return self._subgraphs
        else:
            if identifier in self._subgraphs:
                return self._subgraphs[identifier]

    def node(self, identifier=None):
        """An interface to access the node method of the netwrokx
        graph.
        """
        if identifier == None:
            return self._graph.node
        else:
            if identifier in self._graph.node:
                return self._graph.node[identifier]
        
    def edge(self, identifier=None):
        """GFA edge accessor.

        An interface to the edge method present in networkx.
        It's different from the networkx accessor in that it's not a
        property, so empty brackets are needed to call the networkx
        edge property.
        """
        if identifier == None:
            return self._graph.edge
        if isinstance(identifier, tuple) and len(identifier) >= 2:
            return self.search_edge_by_nodes(identifier)
        else:
            return self.search_edge_by_key(identifier)

    def get(self, key):
        """Return the element pointed by the specified key."""
        try:
            if key in self._graph.node:
                return self.node(key)

            if key in self._subgraphs:
                return self._subgraphs[key]
            
            edge = self.search_edge_by_key(key)
            if edge != None:
                return edge
        except:
            None


    def as_graph_element(self, key):
        """
        Given a key of an existing node, edge or subgraph, return its equivalent
        graph element object.
        """
        element = self.get(key)
        if element == None:
            raise InvalidElementError("No graph element has the given key: {0}".format(key))

        tmp_list = copy.deepcopy(element)
        if isinstance(element, sg.Subgraph):
            return copy.deepcopy(element)
        if 'nid' in element:
            tmp_list.pop('nid')
            tmp_list.pop('sequence')
            tmp_list.pop('slen')
            return node.Node(element['nid'], element['sequence'], element['slen'], opt_fields=tmp_list)
        if 'eid' in element:
            tmp_list.pop('eid')
            tmp_list.pop('from_node')
            tmp_list.pop('from_orn')
            tmp_list.pop('to_node')
            tmp_list.pop('to_orn')
            tmp_list.pop('from_positions')
            tmp_list.pop('to_positions')
            tmp_list.pop('alignment')
            tmp_list.pop('variance')
            tmp_list.pop('distance')
            return ge.Edge(\
                                element['eid'], \
                                element['from_node'], element['from_orn'], \
                                element['to_node'], element['to_orn'], \
                                element['from_positions'], element['to_positions'], \
                                element['alignment'], element['distance'], \
                                element['variance'], \
                                opt_fields=tmp_list\
                            )
               
    def search_edge_by_key(self, key):
        for from_node, to_node, edge_key in self._graph.edges_iter(keys=True):
            if key == edge_key:
                return self._graph.edge[from_node][to_node][edge_key]
        return None

    
    def search_edge_by_nodes(self, nodes):
        """
        If given a tuple with from_node and to_node return all the edges
        between the two nodes.

        If a third element is present in the tuple return the exact edge
        between the two nodes with the key specified by the third element.
        If no match is found return `None`.
        """
        if len(nodes) < 2:
            raise InvalidSearchParameters()
        from_node = nodes [0]
        to_node = nodes [1]

        try:
            if len(nodes) > 2:
                key = nodes[2]
                return self._graph.edge[from_node][to_node][key]
            
            return self._graph.edge[from_node][to_node]
        except:
            return None



    def clear(self):
        """Clear all GFA object elements.

        Call networkx 'clear' method, reset the virtual id counter and
        delete all the subgraphs.
        """
        self._graph.clear()
        self._next_virtual_id = 0
        self._subgraphs = {}

        
    def add_graph_element(self, element):
        """Add a graph element -Node, Edge or Subgraph- to the graph."""
        if isinstance(element, node.Node):
            self.add_node(element)
        elif isinstance(element, ge.Edge):
            self.add_edge(element)
        elif isinstance(element, sg.Subgraph):
            self.add_subgraph(element)
            

    def add_node(self, new_node):
        """Add a graph_element Node to the GFA graph
        using the node id as key,
        its sequence and sequence length will be individual attribute
        on the graph and all the remained optional field will be stored
        on a single list as a node attributes `opt_fields`.
        """       
        if isinstance(new_node, str) and new_node[0] == "S":
            if segment.is_segmentv1(new_node):
                new_node = node.Node.from_line(\
                    segment.SegmentV1.from_string(new_node.strip()))
            else:
                new_node = node.Node.from_line(\
                    segment.SegmentV2.from_string(new_node.strip()))
        
        if not node.is_node(new_node):
            raise node.InvalidNodeError("The object given is not a node.")
        
        self._graph.add_node(\
                                  new_node.nid, \
                                  nid=new_node.nid, \
                                  sequence=new_node.sequence, \
                                  slen=new_node.slen, \
                                  **new_node.opt_fields)
        return True
        
    def add_edge(self, new_edge):
        """Add a graph_element Edge or a networkx edge to the GFA
        graph using  the edge id as key.

        If its id is `*` or `None` the edge will be given a
        **virtual_id**, in either case the original edge id will
        be preserved as edge attribute.

        All edge attributes will be stored as netwrorkx edge
        attributes and its optfields will be stored as a separate
        list in the edge within the attribute `opt_fields`.
        """
        if isinstance(new_edge, str):
          if new_edge[0] == 'L':
              new_edge = ge.Edge.from_line(\
                link.Link.from_string(new_edge.strip()))
          elif new_edge[0] == 'C':
              new_edge = ge.Edge.from_line(\
                containment.Containment.from_string(new_edge.strip()))
          elif new_edge[0] == 'E':
              new_edge =  ge.Edge.from_line(\
                edge.Edge.from_string(new_edge.strip()))
          elif new_edge[0] == 'G':
              new_edge = ge.Edge.from_line(\
                gap.Gap.from_string(new_edge.strip()))
          elif new_edge[0] == 'F':
              new_edge = ge.Edge.from_line(\
                fragment.Fragment.from_string(new_edge.strip()))
          else:
              raise ge.InvalidEdgeError(\
                "The string given doesn't represent a GFA line that could" \
                + " be represented as an edge,\n" \
                + "given: {0}".format(new_edge))
              
        if not ge.is_edge(new_edge):
            raise ge.InvalidEdgeError("The object is not a valid edge.")

        key = new_edge.eid
        if new_edge.eid == None or new_edge.eid == '*':
            key = "virtual_{0}".format(self._get_virtual_id())
        
        self._graph.add_edge( \
                               new_edge.from_node, new_edge.to_node, key=key, \
                               eid=new_edge.eid, \
                               from_node=new_edge.from_node, \
                               from_orn=new_edge.from_orn, \
                               to_node=new_edge.to_node, \
                               to_orn=new_edge.to_orn, \
                               from_positions=new_edge.from_positions, \
                               to_positions=new_edge.to_positions, \
                               alignment=new_edge.alignment, \
                               distance=new_edge.distance ,\
                               variance=new_edge.variance, \
                               **new_edge.opt_fields \
                               )
        return True


    def add_subgraph(self, subgraph):
        # TODO: describe me
        if isinstance(subgraph, str):
            if subgraph[0] == "P":
                subgraph = sg.Subgraph.from_line(\
                    path.Path.from_string(subgraph))
            elif subgraph[0] == "O":
                subgraph = sg.Subgraph.from_line(\
                    group.OGroup.from_string(subgraph))
            elif subgraph[0] == "U":
                subgraph = sg.Subgraph.from_line(\
                    group.UGroup.from_string(subgraph))
            else:
                raise sg.IvalidSubgraphError(\
                    "The string given cannot be represented as a subgraph,\n" \
                    + "given: {0}".format(subgraph))
        
        if not isinstance(subgraph, sg.Subgraph):
            raise sg.InvalidSubgraphError("The object given is not a subgraph.")
        
        key = subgraph.sub_id
        if key == '*':
            key = "virtual_{0}".format(self._get_virtual_id())
        self._subgraphs[key] = copy.deepcopy(subgraph)
        
    def get_subgraph(self, sub_key):
        """Return a GFA subgraph from the parent graph.

        Return a new GFA graph structure with the nodes,
        edges and subgraphs specified in the elements attributes
        of the subgraph object pointed by the id.
        
        The returned GFA is independent from the original object.
        
        :param sub_key: The id of a subgraph present in the GFA graph.
        :returns None: if the subgraph id doesn't exist.
        """
        if not sub_key in self._subgraphs:
            raise InvalidSubgraphError(\
                "There is no subgraph pointed by this key.")

        subgraph = self._subgraphs[sub_key]
        subGFA = GFA()

        for id, orn in subgraph.elements.items():
            # creating a new GFA graph and the add method,
            # the virtual id are recomputed
            subGFA.add_graph_element(self.as_graph_element(id))

        return subGFA

    def subgraph(self, nbunch):
        """Given a bunch of nodes return a graph with
        all the given nodes and the edges between them.

        Interface to the networkx subgraph method.
        Given a collection of nodes return a subgraph with the nodes
        given and all the edges between each pair of nodes.

        All changes apported to the subgraph are reflected to the original
        GFA graph.

        :param nbunch: The nodes.
        """
        return self._graph.subgraph(nbunch)


    def neighbors(self, nid):
        """Return all the nodes id of the nodes connected to
        the given node.
        
        :params nid: The id of the selected node
        """
        return self._graph.neighbors(nid)

    def get_all_reachables(self, nid, weakly=False):
        """Return a GFA subgraph with the connected component
        belonging to the given node.

        :param nid: The id of the node to find the reachable nodes.
        :param weakly: If set to `True` computes the weakly connected
            component for the given node.
        """
        if weakly == True:
            nodes = nx.dfs_tree(nx.MultiGraph(self._graph), nid).nodes()
        else:
            nodes = nx.dfs_tree(self._graph, nid).nodes()
        return GFA(self.subgraph(nodes))

    def search(self, \
               field, \
               value, \
               comparator=VALUE_EQUALITY_COMPARATOR, \
               limit_type=None):
        """Perform a query on the field searching for the value
        specified.
        """
        retval = []
        if limit_type == None:
            retval.extend(self.search_on_nodes(field, value, comparator))
            retval.extend(self.search_on_edges(field, value, comparator))
            retval.extend(self.search_on_subgraph(field, value, comparator))

        elif limit_type == Element.NODE:
            return self.search_on_nodes(field, value, comparator)

        elif limit_type == Element.EDGE:
            return self.search_on_edges(field, value, comparator)

        elif limit_type == Element.SUBGRAPH:
            return self.search_on_subgraph(field, value, comparator)               
        return retval
            
        
    def search_on_nodes(self, field, value, comparator=VALUE_EQUALITY_COMPARATOR):
        retval = []
        for key, data in self._graph.nodes_iter(data=True):
            if field in data and comparator(data[field], value):
                retval.append(key)
        return retval

    
    def search_on_edges(self, field, value, comparator=VALUE_EQUALITY_COMPARATOR):
        retval = []
        for u,v, key, data in self._graph.edges_iter(data=True, keys=True):
            if field in data and comparator(data[field], value):
                retval.append(key)
        return retval

    
    def search_on_subgraph(self, field, value, operator=VALUE_EQUALITY_COMPARATOR):
        retval = []
        for key, data in self._subgraphs.items():
            data = data.as_dict()
            if field in data and operator(data[field], value):
                retval.append(key)
        return retval


    @classmethod
    def from_file(cls, filepath):
        """Parse the given file and return a GFA object.
        """
        pygfa = GFA()
        with open(filepath) as file:
            for line in file:
                line = line.strip()
                if line[0] == 'S':
                    if segment.is_segmentv1(line):
                        pygfa.add_graph_element(\
                            node.Node.from_line(\
                                segment.SegmentV1.from_string(line)))
                    else:
                        pygfa.add_graph_element(\
                            node.Node.from_line(\
                                segment.SegmentV2.from_string(line)))
                elif line[0] == 'L':
                    pygfa.add_graph_element(\
                        ge.Edge.from_line(\
                            link.Link.from_string(line)))
                elif line[0] == 'C':
                    pygfa.add_graph_element(\
                        ge.Edge.from_line(\
                            containment.Containment.from_string(line)))
                elif line[0] == 'E':
                    pygfa.add_graph_element(\
                        ge.Edge.from_line(\
                            edge.Edge.from_string(line)))
                elif line[0] == 'G':
                    pygfa.add_graph_element(\
                        ge.Edge.from_line(\
                            gap.Gap.from_string(line)))
                elif line[0] == 'F':
                    pygfa.add_graph_element(\
                        ge.Edge.from_line(\
                            fragment.Fragment.from_string(line)))
                elif line[0] == 'P':
                    pygfa.add_graph_element(\
                        sg.Subgraph.from_line(\
                            path.Path.from_string(line)))
                elif line[0] == 'O':
                    pygfa.add_graph_element(\
                        sg.Subgraph.from_line(\
                            group.OGroup.from_string(line)))
                elif line[0] == 'U':
                    pygfa.add_graph_element(\
                        sg.Subgraph.from_line(\
                            group.UGroup.from_string(line)))
        return pygfa

    
    def pprint(self):
        """A basic pretty print function for nodes and edges.
        """
        string = "\nGRAPH:\nNodes: [\n"
        for node, datas in self._graph.nodes_iter(data=True):
            string += str(node) + "\t: {"
            for name, data in datas.items():
                string += str(name) + ": " + str(data) + "\t"
            string += "}\n"
        string += "]\n"

        string += "\nEdges: [\n"    
        for from_node, to_node, key, datas in self._graph.edges_iter( \
                                                            keys=True,\
                                                            data=True):
            string += str(key) + "\t: {"
            for name, data in datas.items():
                string += str(name) + ": " + str(data) + "\t"
            string += "}\n"
        string += "]\n"

        string += "\nSubgraphs: [\n"    
        for key, data in self._subgraphs.items():
            string += str(key) + "\t: {" + str(data) +  "}\n"
                                   
        string += "]\n"
        return string


    def dump(self, gfa_version=1):
        if gfa_version == 1:
            return gs1.serialize_gfa(self)
        elif gfa_version == 2:
            return gs2.serialize_gfa(self)

        raise ValueError("Invalid GFA output version.")

if __name__ == '__main__':
    pass
