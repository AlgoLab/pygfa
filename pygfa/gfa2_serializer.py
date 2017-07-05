"""@package gfa2_serializer
"""

# SUPER TODO: refactor this code and gfa1_serialzer to avoid the HORDES
# of duplicated code they contain

from pygfa.graph_element.parser import line, field_validator as fv
from pygfa.graph_element.parser import segment, edge, group, containment, path, fragment, link
from pygfa.graph_element import edge as ge, node, subgraph
import copy, logging
import networkx as nx
import pygfa.gfa

# TODO: is this a good idea?
serializer_logger = logging.getLogger(__name__)
serializer_logger.setLevel(logging.DEBUG)

SERIALIZATION_ERROR_MESSAGGE = "Couldn't serialize object identified by: "
DEFAULT_IDENTIFIER = "no identifier given."

def _remove_common_edge_fields (edge_dict):
    edge_dict.pop ('eid')
    edge_dict.pop ('from_node')
    edge_dict.pop ('from_orn')
    edge_dict.pop ('to_node')
    edge_dict.pop ('to_orn')
    edge_dict.pop ('from_positions')
    edge_dict.pop ('to_positions')
    edge_dict.pop ('alignment')
    edge_dict.pop ('distance')
    edge_dict.pop ('variance')

    
def _serialize_opt_fields (opt_fields):
    fields = []
    for key, opt_field in opt_fields.items ():
        if line.is_optfield (opt_field):
            fields.append (str (opt_field))
    return fields


SEGMENT_FIELDS = [fv.GFA2_ID, fv.GFA2_INT, fv.GFA2_SEQUENCE]
EDGE_FIELDS = [fv.GFA2_OPTIONAL_ID, fv.GFA2_REFERENCE, fv.GFA2_REFERENCE, \
            fv.GFA2_POSITION, fv.GFA2_POSITION, fv.GFA2_POSITION, fv.GFA2_POSITION, fv.GFA2_ALIGNMENT]

FRAGMENT_FIELDS = [fv.GFA2_ID, fv.GFA2_REFERENCE, fv.GFA2_POSITION, \
                fv.GFA2_POSITION, fv.GFA2_POSITION, fv.GFA2_POSITION, fv.GFA2_ALIGNMENT]

GAP_FIELDS = [fv.GFA2_OPTIONAL_ID, fv.GFA2_REFERENCE, fv.GFA2_REFERENCE, \
            fv.GFA2_INT, fv.GFA2_OPTIONAL_INT]

UGROUP_FIELDS = [fv.GFA2_OPTIONAL_ID, fv.GFA2_IDS]
OGROUP_FIELDS = [fv.GFA2_OPTIONAL_ID, fv.GFA2_REFERENCES]

def _check_fields (fields, required_fields):
    """!
    Check if each field has the correct format as stated from the specification.
    """
    try:
        for field in range (0, len (required_fields)):
            if not fv.is_valid (fields[field], required_fields[field]):
                return False
        return True
    except Exception:
        return False

    
def _are_fields_defined (fields):
    try:
        for field in fields:
            if field == None:
                return False
    except Exception:
        return False
    return True


class GFA2SerializationError (Exception): pass
    
################################################################################
# NODE SERIALIZER
################################################################################
def serialize_node (node, identifier=DEFAULT_IDENTIFIER):
    """!
    Serialize to the GFA2 specification a Graph Element Node or a
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
    try:
        if isinstance (node, dict):
        
            node_dict = copy.deepcopy (node)

            defined_fields = [ \
                                   node_dict.pop ('nid'), \
                                   node_dict.pop ('sequence'), \
                                   node_dict.pop ('slen') \
                            ]
            
            fields = ["S"]
            fields.append (str (node['nid']))

            fields.append (str (node['slen'] if node['slen'] != None else 0))
            fields.append (str (node['sequence']))
            
            fields.extend (_serialize_opt_fields (node_dict))
            
        else:

            defined_fields = [ \
                                   node.nid, \
                                   node.sequence, \
                                   node.slen \
                            ]
            
            fields = ["S"]
            fields.append (str (node.nid))
            
            fields.append (str (node.slen if node.slen != None else 0))
            fields.append (str (node.sequence))

            fields.extend (_serialize_opt_fields (node.opt_fields))


        if not _are_fields_defined (defined_fields) or \
           not _check_fields (fields[1:], SEGMENT_FIELDS):
            raise GFA2SerializationError ()

        return str.join ("\t", fields)

    # TODO: see if ValueError is ever raised
    except (AttributeError, KeyError, ValueError, GFA2SerializationError) as e:
        serializer_logger.debug (SERIALIZATION_ERROR_MESSAGGE + str (identifier))            
        return ""


################################################################################
# EDGE SERIALIZER
################################################################################

def serialize_edge (edge, identifier=DEFAULT_IDENTIFIER):
    """!
    Converts to a GFA2 line the given edge.
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
                return _serialize_to_fragment (edge, identifier)
            elif edge['distance'] != None or \
              edge['variance'] != None: # edge is a gap
                return _serialize_to_gap (edge, identifier)
            else:
                return _serialize_to_edge (edge, identifier)
        except KeyError as ke:
            serializer_logger.debug (SERIALIZATION_ERROR_MESSAGGE + str (identifier))
            return ""
    else:
        try:
            if edge.eid == None: # edge is a fragment
                return _serialize_to_fragment (edge, identifier)
            elif edge.distance != None or \
              edge.variance != None: # edge is a gap
                return _serialize_to_gap (edge, identifier)
            else:
                return _serialize_to_edge (edge)
            
        except AttributeError as ae:
            serializer_logger.debug (SERIALIZATION_ERROR_MESSAGGE + str (identifier))
            return ""

        
def _serialize_to_fragment (edge, identifier=DEFAULT_IDENTIFIER):
    if not isinstance (identifier, str):
        identifier = "'{0}' - id of type {1}.".format (\
                                                             str (identifier), \
                                                             type (identifier) \
                                                        )

    try:
        if isinstance (edge, dict):

            edge_dict = copy.deepcopy (edge)

            _remove_common_edge_fields (edge_dict)


            defined_fields = [\
                                edge['from_node'], \
                                edge['to_node'], \
                                edge['to_orn'], \
                                edge['from_positions'][0], edge['from_positions'][1], \
                                edge['to_positions'][0], edge['to_positions'][1], \
                                edge['alignment'] \
                            ]

            fields = ["F"]
            fields.append (str (edge['from_node']))
            fields.append (str (edge['to_node']) + str (edge['to_orn']))
            fields.append (str (edge['from_positions'][0]))
            fields.append (str (edge['from_positions'][1]))
            fields.append (str (edge['to_positions'][0]))
            fields.append (str (edge['to_positions'][1]))
            fields.append (str (edge['alignment']))

            fields.extend (_serialize_opt_fields (edge_dict))
            
        else:

            defined_fields = [\
                                edge.from_node, \
                                edge.to_node, \
                                edge.to_orn, \
                                edge.from_positions[0], edge.from_positions[1], \
                                edge.to_positions[0], edge.to_positions[1], \
                            ]
            
            fields = ["F"]
            fields.append (str (edge.from_node))
            fields.append (str (edge.to_node) + str (edge.to_orn))

            fields.append (str (edge.from_positions[0]))
            fields.append (str (edge.from_positions[1]))
            fields.append (str (edge.to_positions[0]))
            fields.append (str (edge.to_positions[1]))

            fields.extend (_serialize_opt_fields (edge.opt_fields))

        if not _are_fields_defined (defined_fields) or \
           not _check_fields (fields[1:], FRAGMENT_FIELDS):
            raise GFA2SerializationError ()
            
        return str.join ("\t", fields)

    except (KeyError, ValueError, AttributeError, GFA2SerializationError) as e:
        serializer_logger.debug (SERIALIZATION_ERROR_MESSAGGE + str (identifier))            
        return ""
    

def _serialize_to_gap (edge, identifier=DEFAULT_IDENTIFIER):
    if not isinstance (identifier, str):
        identifier = "'{0}' - id of type {1}.".format (\
                                                             str (identifier), \
                                                             type (identifier) \
                                                        )

    try:
        if isinstance (edge, dict):

            edge_dict = copy.deepcopy (edge)
            _remove_common_edge_fields (edge_dict)


            defined_fields = [\
                                edge['eid'], \
                                edge['from_node'], \
                                edge['from_orn'], \
                                edge['to_node'], \
                                edge['to_orn'], \
                                edge['distance'], \
                                edge['variance'] \
                            ]
            
            fields = ["G"]
            
            fields.append (str (edge['eid']))
            fields.append (str (edge['from_node']) + str (edge['from_orn']))
            fields.append (str (edge['to_node']) + str (edge['to_orn']))

            fields.append (str (edge['distance']))
            fields.append (str (edge['variance']))

            fields.extend (_serialize_opt_fields (edge_dict))
            return str.join ("\t", fields)
        
        else:

            defined_fields = [\
                                edge.eid, \
                                edge.from_node, \
                                edge.from_orn, \
                                edge.to_node, \
                                edge.to_orn, \
                                edge.distance, \
                                edge.variance \
                            ]

            fields = ["G"]

            fields.append (str (edge.eid))
            fields.append (str (edge.from_node) + str (edge.from_orn))
            fields.append (str (edge.to_node) + str (edge.to_orn))

            fields.append (str (edge.distance))
            fields.append (str (edge.variance))

            fields.extend (_serialize_opt_fields (edge.opt_fields))

        if not _are_fields_defined (defined_fields) or \
           not _check_fields (fields[1:], GAP_FIELDS):
            raise GFA2SerializationError ()
            
        return str.join ("\t", fields)

    except (AttributeError, KeyError, GFA2SerializationError) as e:
        serializer_logger.debug (SERIALIZATION_ERROR_MESSAGGE + str (identifier))            
        return ""

            
def _serialize_to_edge (edge, identifier=DEFAULT_IDENTIFIER):
    if not isinstance (identifier, str):
        identifier = "'{0}' - id of type {1}.".format (\
                                                             str (identifier), \
                                                             type (identifier) \
                                                        )

    try:                                                        
        if isinstance (edge, dict):

            edge_dict = copy.deepcopy (edge)
            _remove_common_edge_fields (edge_dict)

            defined_fields = [ \
                                edge['eid'], \
                                edge['from_node'], \
                                edge['from_orn'], \
                                edge['to_node'], \
                                edge['to_orn'], \
                                edge['from_positions'][0], edge['from_positions'][1], \
                                edge['to_positions'][0], edge['to_positions'][1], \
                                edge['alignment'] \
                             ]
            
            fields = ["E"]
            
            fields.append (str (edge['eid']))
            fields.append (str (edge['from_node']) + str (edge['from_orn']))
            fields.append (str (edge['to_node']) + str (edge['to_orn']))
            fields.append (str (edge['from_positions'][0]))
            fields.append (str (edge['from_positions'][1]))
            fields.append (str (edge['to_positions'][0]))
            fields.append (str (edge['to_positions'][1]))
            fields.append (str (edge['alignment']))

            fields.extend (_serialize_opt_fields (edge_dict))
            
        
        else:

            defined_fields = [ \
                                edge.eid, \
                                edge.from_node, \
                                edge.from_orn, \
                                edge.to_node, \
                                edge.to_orn, \
                                edge.from_positions[0], edge.from_positions[1], \
                                edge.to_positions[0], edge.to_positions[1], \
                                edge.alignment \
                            ]
            
            fields = ["E"]

            fields.append (str (edge.eid))
            fields.append (str (edge.from_node) + str (edge.from_orn))
            fields.append (str (edge.to_node) + str (edge.to_orn))

            fields.append (str (edge.from_positions[0]))
            fields.append (str (edge.from_positions[1]))
            fields.append (str (edge.to_positions[0]))
            fields.append (str (edge.to_positions[1]))
            
            fields.append (str (edge.alignment))

            fields.extend (_serialize_opt_fields (edge.opt_fields))

        
        if not _are_fields_defined (defined_fields) or \
           not _check_fields (fields[1:], EDGE_FIELDS):
            raise GFA2SerializationError ()
        
        return str.join ("\t", fields)

    except (KeyError, AttributeError, GFA2SerializationError) as e:
        serializer_logger.debug (SERIALIZATION_ERROR_MESSAGGE + str (identifier))            
        return ""


################################################################################
# SUBGRAPH SERIALIZER
################################################################################
def are_elements_oriented (subgraph_elements):
    for id, orientation in subgraph_elements.items ():
        if orientation == None:
            return False
    return True

def _serialize_subgraph_elements (subgraph_elements, gfa=None):
    """!
    Serialize the elements belonging to a subgraph.
    Check if the orientation is provided for each element of the
    subgraph.

    @param subgraph_elements The elements of a Subgraph
    """
    return str.join (" ", [str (id) + ((str (orientation)) if orientation != None else "") \
                               for id, orientation in subgraph_elements.items ()])
    
def serialize_subgraph (subgraph, identifier=DEFAULT_IDENTIFIER):
    """!
    """
    # TODO: describe me
    if not isinstance (identifier, str):
        identifier = "'{0}' - id of type {1}.".format (\
                                                             str (identifier), \
                                                             type (identifier) \
                                                        )

    try:
        if isinstance (subgraph, dict):

            subgraph_dict = copy.deepcopy (subgraph)

            defined_fields = [\
                                subgraph_dict.pop ('sub_id'), \
                                subgraph_dict.pop ('elements') \
                             ]
                                
            fields = ["O"] if are_elements_oriented (subgraph['elements']) else ["U"] 
            fields.append (str (subgraph['sub_id']))
            fields.append (_serialize_subgraph_elements (subgraph['elements'], gfa))

            if 'overlaps' in subgraph:
                subgraph_dict.pop ('overlaps')

            fields.extend (_serialize_opt_fields (subgraph_dict))

        else:
        
            opt_fields = copy.deepcopy (subgraph.opt_fields)

            defined_fields = [\
                                subgraph.sub_id, \
                                subgraph.elements \
                             ]
            

            fields = ["O"] if are_elements_oriented (subgraph.elements) else ["U"] 
            fields.append (str (subgraph.sub_id))
            fields.append (_serialize_subgraph_elements (subgraph.elements, gfa))

            if 'overlaps' in subgraph.opt_fields:
                opt_fields.pop ('overlaps')

            fields.extend (_serialize_opt_fields (subgraph.opt_fields))

        group_fields = OGROUP_FIELDS if fields[0] == "O" else UGROUP_FIELDS
        if not _are_fields_defined (defined_fields) or \
           not _check_fields (fields[1:], group_fields):
            raise GFA2SerializationError ()
        
        return str.join ("\t", fields)
            
    except (KeyError, ValueError, AttributeError, GFA2SerializationError) as e:
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
    @write_header If set to True put a GFA2 header as first line.
    """
    if not is_graph_serializable (graph):
        raise ValueError ("The object to serialize must be an instance of a networkx.DiGraph.")

    if write_header == True:
        string_serialize = "H\tVN:Z:2.0\n"

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
    Serialize a GFA object into a GFA2 file.
    """

    # TODO: maybe process  the header fields here

    gfa_serialize = serialize_graph (gfa._graph, write_header=True) # header=True?

    for sub_id, subgraph in gfa.subgraphs().items ():
        subgraph_serialize = serialize_subgraph (subgraph, sub_id)
        if len (subgraph_serialize) > 0:
            gfa_serialize += subgraph_serialize + "\n"

    return gfa_serialize

if __name__ == '__main__':
    pass
