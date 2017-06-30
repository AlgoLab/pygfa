"""@package gfa1_serializer
"""

from parser import line, field_validator as fv
from parser.lines import segment, edge, group, containment, path, fragment, link
from graph_element import edge as ge, node, subgraph
import copy, logging
import networkx as nx
import gfa

# TODO: is this a good idea?
serializer_logger = logging.getLogger(__name__)
serializer_logger.setLevel(logging.DEBUG)

SERIALIZATION_ERROR_MESSAGGE = "Couldn't serialize object identified by: "
DEFAULT_IDENTIFIER = "no identifier given."


################################################################################
# NODE SERIALIZER
################################################################################
def serialize_node (node, identifier=DEFAULT_IDENTIFIER):
    """!
    Serialize to the GFA1 specification a Graph Element Node or a
    dictionary that has the same informations.
    If the object cannot be serialized to GFA an empty string
    is returned.

    @param node A Graph Element Node or a dictionary
    @identifier If set help gaining useful debug information.
    """
    if not isinstance (identifier, str):
        identifier = "'{0}' - id of type {1}.".format (\
                                                             str (identifier), \
                                                             type (identifier) \
                                                        )

    if isinstance (node, dict):
        try:
            node_dict = copy.deepcopy (node)
            node_dict.pop ('nid')
            node_dict.pop ('sequence')
            node_dict.pop ('slen')
            
            fields = ["S"]
            fields.append (str (node['nid']))
            fields.append (str (node['sequence']))
            if node['slen'] != None:
                fields.append ("LN:i:" + str (node['slen']))

            for key, opt_field in node_dict.items ():
                if line.is_optfield (opt_field):
                    fields.append (str (opt_field))

            return str.join ("\t", fields)

        except KeyError as ke:
            serializer_logger.debug (SERIALIZATION_ERROR_MESSAGGE + str (identifier))
            return ""
        
    else:
        try:
            fields = ["S"]
            fields.append (str (node.nid))
            fields.append (str (node.sequence))
            if node.slen != None:
                fields.append (str (node.slen))

            for key, opt_field in node.opt_fields.items ():
                if line.is_optfield (opt_field):
                    fields.append (str (opt_field))

            return str.join ("\t", fields)

        except AttributeError as ae:
            serializer_logger.debug (SERIALIZATION_ERROR_MESSAGGE + str (identifier))            
            return ""

################################################################################
# EDGE SERIALIZER
################################################################################

def serialize_edge (edge, identifier=DEFAULT_IDENTIFIER):
    """!
    Converts to a GFA1 line the given edge.
    Fragments and Gaps cannot be represented in GFA1 specification,
    so they are not serialized.

    # TODO explain better
    """
    if not isinstance (identifier, str):
        identifier = "'{0}' - id of type {1}.".format (\
                                                             str (identifier), \
                                                             type (identifier) \
                                                        )

    if isinstance (edge, dict):
        try:
            if edge['eid'] == None: # edge is a fragment
                return ""
            elif edge['distance'] != None or \
              edge['variance'] != None: # edge is a gap
                return ""
            elif 'pos' in edge: # edge is a containment
                return _serialize_to_containment (edge, identifier)
            else:
                return _serialize_to_link (edge, identifier)
        except KeyError as ke:
            serializer_logger.debug (SERIALIZATION_ERROR_MESSAGGE + str (identifier))
            return ""
    else:
        try:
            if edge.eid == None: # edge is a fragment
                return ""
            elif edge.distance != None or \
              edge.variance != None: # edge is a gap
                return ""
            elif 'pos' in edge.opt_fields: # edge is a containment
                return _serialize_to_containment (edge)
            else:
                return _serialize_to_link (edge)
            
        except AttributeError as ae:
            serializer_logger.debug (SERIALIZATION_ERROR_MESSAGGE + str (identifier))
            return ""

            
def _serialize_to_containment (containment, identifier=DEFAULT_IDENTIFIER):
    if not isinstance (identifier, str):
        identifier = "'{0}' - id of type {1}.".format (\
                                                             str (identifier), \
                                                             type (identifier) \
                                                        )

    if isinstance (containment, dict):
        try:
            containment_dict = copy.deepcopy (containment)
            containment_dict.pop ('eid')
            containment_dict.pop ('from_node')
            containment_dict.pop ('from_orn')
            containment_dict.pop ('to_node')
            containment_dict.pop ('to_orn')
            containment_dict.pop ('from_positions')
            containment_dict.pop ('to_positions')
            containment_dict.pop ('alignment')
            containment_dict.pop ('distance')
            containment_dict.pop ('variance')
            containment_dict.pop ('pos')

            fields = ["C"]
            fields.append (str (containment['from_node']))
            fields.append (str (containment['from_orn']))
            fields.append (str (containment['to_node']))
            fields.append (str (containment['to_orn']))
            fields.append (str (containment['pos'].value))

            if fv.is_gfa1_cigar (containment['alignment']):
                fields.append (str (containment['alignment']))
            else:
                fields.append ("*")
                
            if not containment['eid'] in (None, '*'):
                fields.append ("ID:Z:" + str (containment['eid']))

            for key, opt_field in containment_dict.items ():
                if line.is_optfield (opt_field):
                    fields.append (str (opt_field))

            return str.join ("\t", fields)
            
        except KeyError as ke:
            serializer_logger.debug (SERIALIZATION_ERROR_MESSAGGE + str (identifier))            
            return ""
    else:
        try:
            fields = ["C"]
            opt_fields = copy.deepcopy (containment.opt_fields)
            opt_fields.pop ('pos')
            
            fields.append (str (containment.from_node))
            fields.append (str (containment.from_orn))
            fields.append (str (containment.to_node))
            fields.append (str (containment.to_orn))
            fields.append (str (containment.opt_fields['pos'].value))

            if fv.is_gfa1_cigar (containment.alignment):
                fields.append (str (containment.alignment))
            else:
                fields.append ("*")
            
            if not containment.eid in (None, '*'):
                fields.append ("ID:Z:" + str (containment.eid))
                               
            for key, opt_field in opt_fields.items ():
                if line.is_optfield (opt_field):
                    fields.append (str (opt_field))

            return str.join ("\t", fields)

        except AttributeError as ae:
            serializer_logger.debug (SERIALIZATION_ERROR_MESSAGGE + str (identifier))            
            return ""
        

def _serialize_to_link (link, identifier=DEFAULT_IDENTIFIER):
    if not isinstance (identifier, str):
        identifier = "'{0}' - id of type {1}.".format (\
                                                             str (identifier), \
                                                             type (identifier) \
                                                        )

    if isinstance (link, dict):
        try:
            link_dict = copy.deepcopy (link)
            link_dict.pop ('eid')
            link_dict.pop ('from_node')
            link_dict.pop ('from_orn')
            link_dict.pop ('to_node')
            link_dict.pop ('to_orn')
            link_dict.pop ('from_positions')
            link_dict.pop ('to_positions')
            link_dict.pop ('alignment')
            link_dict.pop ('distance')
            link_dict.pop ('variance')

            fields = ["L"]
            fields.append (str (link['from_node']))
            fields.append (str (link['from_orn']))
            fields.append (str (link['to_node']))
            fields.append (str (link['to_orn']))

            if fv.is_gfa1_cigar (link['alignment']):
                fields.append (str (link['alignment']))
            else:
                fields.append ("*")
                
            if not link['eid'] in (None, '*'):
                fields.append ("ID:Z:" + str (link['eid']))

            for key, opt_field in link_dict.items ():
                if line.is_optfield (opt_field):
                    fields.append (str (opt_field))

            return str.join ("\t", fields)
            
        except KeyError as ke:
            serializer_logger.debug (SERIALIZATION_ERROR_MESSAGGE + str (identifier))            
            return ""
    else:
        try:
            fields = ["L"]

            fields.append (str (link.from_node))
            fields.append (str (link.from_orn))
            fields.append (str (link.to_node))
            fields.append (str (link.to_orn))

            if fv.is_gfa1_cigar (link.alignment):
                fields.append (str (link.alignment))
            else:
                fields.append ("*")
            
            if not link.eid in (None, '*'):
                fields.append ("ID:Z:" + str (link.eid))
                               
            for key, opt_field in link.opt_fields.items ():
                if line.is_optfield (opt_field):
                    fields.append (str (opt_field))

            return str.join ("\t", fields)

        except AttributeError as ae:
            serializer_logger.debug (SERIALIZATION_ERROR_MESSAGGE + str (identifier))            
            return ""


################################################################################
# SUBGRAPH SERIALIZER
################################################################################

def point_to_node (gfa, node_id):
    """!
    Check if the given \p node_id point
    to a node.Node object into the \p gfa GFA object.
    """
    return gfa.node (node_id) != None

def _serialize_subgraph_elements (subgraph_elements, gfa=None):
    """!
    Serialize the elements belonging to a subgraph.
    Check if the orientation is provided for each element of the
    subgraph.

    If \p gfa is set, each element can be tested wheter it
    is a node or another element of the GFA graph.
    Only nodes (segments) will be (and could be) serialized
    to elements of the Path.

    @param subgraph A Graph Element Subgraph
    @param gfa The GFA object that contain the \p subgraph
    """
    try:
        elements = []
        for id, orientation in subgraph_elements.items ():
            if orientation != None and \
               gfa != None and \
               point_to_node (gfa, id):

               elements.append (str (id) + str (orientation))

        return str.join (",", elements)
            
    except Exception as e:
        raise ValueError (e) # This exception will be caught from serialie_subgraph

def serialize_subgraph (subgraph, identifier=DEFAULT_IDENTIFIER, gfa=None):
    """!
    """
    # TODO: describe me
    if not isinstance (identifier, str):
        identifier = "'{0}' - id of type {1}.".format (\
                                                             str (identifier), \
                                                             type (identifier) \
                                                        )

    if isinstance (subgraph, dict):
        try:
            subgraph_dict = copy.deepcopy (subgraph)
            subgraph_dict.pop ('sub_id')
            subgraph_dict.pop ('elements')

            fields = ["P"]
            fields.append (subgraph['sub_id'])
            fields.append (_serialize_subgraph_elements (subgraph['elements'], gfa))

            if 'overlaps' in subgraph:
                subgraph_dict.pop ('overlaps')
                fields.append (str.join (",", subgraph['overlaps'].value))
            else:
                fields.append ("*")

            for key, opt_field in subgraph_dict.items ():
                if line.is_optfield (opt_field):
                    fields.append (str (opt_field))

            return str.join ("\t", fields)

        except (ValueError, KeyError) as e:
            serializer_logger.debug (SERIALIZATION_ERROR_MESSAGGE + str (identifier))
            return ""
    else:
        try:
            opt_fields = copy.deepcopy (subgraph.opt_fields)

            fields = ["P"]
            fields.append (subgraph.sub_id)
            fields.append (_serialize_subgraph_elements (subgraph.elements, gfa))

            if 'overlaps' in subgraph.opt_fields:
                opt_fields.pop ('overlaps')
                fields.append (str.join (",", subgraph.opt_fields['overlaps'].value))
            else:
                fields.append ("*")

            for key, opt_field in opt_fields.items ():
                if line.is_optfield (opt_field):
                    fields.append (str (opt_field))

            return str.join ("\t", fields)
            
        except (ValueError, AttributeError) as e:
            serializer_logger.debug (SERIALIZATION_ERROR_MESSAGGE + str (identifier))            
            return ""

    
################################################################################
# OBJECT SERIALIZER
################################################################################
def serialize (object, identifier=DEFAULT_IDENTIFIER):
    if isinstance (object, dict):
        
        if 'nid' in object:
            return serialize_node (object, identifier)
        elif 'eid' in object:
            return serialize_edge (object, identifier)
        elif 'sub_id' in object:
            return serialize_subgraph (object, identifier)
    else:
        if hasattr (object, '_nid') or hasattr (object, 'nid'):
            return serialize_node (object, identifier)
        elif hasattr (object, '_eid') or hasattr (object, 'eid'):
            return serialize_edge (object, identifier)
        elif hasattr (object, '_sub_id') or hasattr (object, 'sub_nid'):
            return serialize_subgraph (object, identifier)

    return "" # if it's not possible to serialize, return an empty string 

################################################################################
# SERIALIZE GRAPH
################################################################################

def is_graph_serializable (object):
    return isinstance (object, nx.DiGraph)

def serialize_graph (graph, write_header=True):
    """!
    Serialize a networkx.DiGraph or a derivative object.

    @param graph A networkx.DiGraph instance.
    @write_header If set to True put a GFA1 header as first line.
    """
    if not is_graph_serializable (graph):
        raise ValueError ("The object to serialize must be an instance of a networkx.DiGraph.")

    if write_header == True:
        string_serialize = "H\tVN:Z:1.0\n"

    for node_id, node in graph.nodes_iter (data=True):
        node_serialize = serialize_node (node, node_id)
        if len (node_serialize) > 0:
            string_serialize += node_serialize + "\n"

    for from_node, to_node, key in graph.edges_iter (keys=True):
        edge_serialize = serialize_edge (graph.edge[from_node][to_node][key], key)
        if len (edge_serialize) > 0:
            string_serialize += edge_serialize + "\n"

    return string_serialize


def serialize_gfa (gfa):
    """!
    Serialize a GFA object into a GFA1 file.
    """

    # TODO: may be process header her, maybe header optional fields
    # could be saved... think about it

    gfa_serialize = serialize_graph (gfa._graph, write_header=True) # header=True?

    for sub_id, subgraph in gfa.subgraphs().items ():
        subgraph_serialize = serialize_subgraph (subgraph, sub_id, gfa)
        if len (subgraph_serialize) > 0:
            gfa_serialize += subgraph_serialize + "\n"

    return gfa_serialize
