"""
GFA1 Serializer for nodes, edge, Subgraphs and networkx graphs.

Can serialize either one of the object from the group mentioned
before or from a dictionary with equivalent key.
"""
import copy
import logging

import networkx as nx

from pygfa.graph_element.parser import line, field_validator as fv
from pygfa.graph_element.parser import segment, edge, group, containment, path, fragment, link
from pygfa.graph_element import edge as ge, node, subgraph
from pygfa.serializer import utils
from pygfa import gfa

class GFA1SerializationError(Exception): pass

serializer_logger = logging.getLogger(__name__)
    
DEFAULT_IDENTIFIER = "no identifier given."

SEGMENT_FIELDS = [fv.GFA1_NAME, fv.GFA1_SEQUENCE]
LINK_FIELDS = [\
    fv.GFA1_NAME, \
    fv.GFA1_ORIENTATION, \
    fv.GFA1_NAME, \
    fv.GFA1_ORIENTATION, \
    fv.GFA1_CIGAR]

CONTAINMENT_FIELDS = [\
    fv.GFA1_NAME, \
    fv.GFA1_ORIENTATION, \
    fv.GFA1_NAME, \
    fv.GFA1_ORIENTATION, \
    fv.GFA1_INT, \
    fv.GFA1_CIGAR]

PATH_FIELDS = [\
    fv.GFA1_NAME, \
    fv.GFA1_NAMES, \
    fv.GFA1_CIGARS]
################################################################################
# NODE SERIALIZER
################################################################################
def serialize_node(node, identifier=DEFAULT_IDENTIFIER):
    """Serialize to the GFA1 specification a Graph Element Node or a
    dictionary that has the same informations.

    :param node: A Graph Element Node or a dictionary.
    :param identifier: If set help gaining useful debug information.
    :return "": If the object cannot be serialized to GFA.
    """
    identifier = utils._check_identifier(identifier)
    try:
        if isinstance(node, dict):

            node_dict = copy.deepcopy(node)
            defined_fields = [ \
                                node_dict.pop('nid'), \
                                node_dict.pop('sequence') \
                             ]
            node_dict.pop('slen')
            fields = ["S"]
            fields.append(str(node['nid']))
            fields.append(str(node['sequence']))
            if node['slen'] != None:
                fields.append("LN:i:" + str(node['slen']))

            fields.extend(utils._serialize_opt_fields(node_dict))
        else:
            defined_fields = [ \
                                node.nid, \
                                node.sequence
                             ]
            fields = ["S"]
            fields.append(str(node.nid))
            fields.append(str(node.sequence))
            if node.slen != None:
                fields.append("LN:i:" + str(node.slen))
            fields.extend(utils._serialize_opt_fields(node.opt_fields))
            
        if not utils._are_fields_defined(defined_fields) or \
           not utils._check_fields(fields[1:], SEGMENT_FIELDS):
            raise GFA1SerializationError("Required node elements " \
                                        + "missing or invalid.")

        return str.join("\t", fields)

    except (KeyError, AttributeError, GFA1SerializationError) as e:
        serializer_logger.debug(utils._format_exception(identifier, e))            
        return ""

################################################################################
# EDGE SERIALIZER
################################################################################
def serialize_edge(edge, identifier=DEFAULT_IDENTIFIER):
    """Converts to a GFA1 line the given edge.

    Fragments and Gaps cannot be represented in GFA1 specification,
    so they are not serialized.
    """
    identifier = utils._check_identifier(identifier)
    try:
        if isinstance(edge, dict):
            if edge['eid'] == None: # edge is a fragment
                raise GFA1SerializationError("Cannot serialize Fragment " \
                                        + "to GFA1.")
            elif edge['distance'] != None or \
              edge['variance'] != None: # edge is a gap
                raise GFA1SerializationError("Cannot serialize GAP " \
                                        + "to GFA1.")
            elif 'pos' in edge: # edge is a containment
                return _serialize_to_containment(edge, identifier)
            else:
                return _serialize_to_link(edge, identifier)
        else:
            if edge.eid == None: # edge is a fragment
                raise GFA1SerializationError("Cannot serialize Fragment " \
                                        + "to GFA1.")
            elif edge.distance != None or \
              edge.variance != None: # edge is a gap
                raise GFA1SerializationError("Cannot serialize GAP " \
                                        + "to GFA1.")
            elif 'pos' in edge.opt_fields: # edge is a containment
                return _serialize_to_containment(edge)
            else:
                return _serialize_to_link(edge)
    except (KeyError, AttributeError, GFA1SerializationError) as e:
        serializer_logger.debug(utils._format_exception(identifier, e))
        return ""

    
def _serialize_to_containment(containment_, identifier=DEFAULT_IDENTIFIER):
    identifier = utils._check_identifier(identifier)
    try:
        if isinstance(containment_, dict):
            containment_dict = copy.deepcopy(containment_)
            utils._remove_common_edge_fields(containment_dict)
            containment_dict.pop('pos')
            defined_fields = [ \
                                containment_['from_node'], \
                                containment_['from_orn'], \
                                containment_['to_node'], \
                                containment_['to_orn'], \
                                containment_['alignment'], \
                                containment_['pos'].value
                             ]
            fields = ["C"]
            fields.append(str(containment_['from_node']))
            fields.append(str(containment_['from_orn']))
            fields.append(str(containment_['to_node']))
            fields.append(str(containment_['to_orn']))
            fields.append(str(containment_['pos'].value))

            if fv.is_gfa1_cigar(containment_['alignment']):
                fields.append(str(containment_['alignment']))
            else:
                fields.append("*")
                
            if not containment_['eid'] in(None, '*'):
                fields.append("ID:Z:" + str(containment_['eid']))

            fields.extend(utils._serialize_opt_fields(containment_dict))
        else:
            defined_fields = [ \
                                containment_.from_node, \
                                containment_.from_orn, \
                                containment_.to_node, \
                                containment_.to_orn, \
                                containment_.alignment, \
                                containment_.opt_fields['pos'].value \
                             ]
            fields = ["C"]
            opt_fields = copy.deepcopy(containment_.opt_fields)
            opt_fields.pop('pos')
            fields.append(str(containment_.from_node))
            fields.append(str(containment_.from_orn))
            fields.append(str(containment_.to_node))
            fields.append(str(containment_.to_orn))
            fields.append(str(containment_.opt_fields['pos'].value))

            if fv.is_gfa1_cigar(containment_.alignment):
                fields.append(str(containment_.alignment))
            else:
                fields.append("*")
            if not containment_.eid in(None, '*'):
                fields.append("ID:Z:" + str(containment_.eid))
            fields.extend(utils._serialize_opt_fields(opt_fields))

        if not utils._are_fields_defined(defined_fields) or \
           not utils._check_fields(fields[1:], CONTAINMENT_FIELDS):
            raise GFA1SerializationError()

        return str.join("\t", fields)

    except(KeyError, AttributeError, GFA1SerializationError) as e:
        serializer_logger.debug(utils._format_exception(identifier, e))            
        return ""
        

def _serialize_to_link(link_, identifier=DEFAULT_IDENTIFIER):
    identifier = utils._check_identifier(identifier)
    try:
        if isinstance(link_, dict):
            link_dict = copy.deepcopy(link_)
            utils._remove_common_edge_fields(link_dict)
            defined_fields = [ \
                                link_['from_node'], \
                                link_['from_orn'], \
                                link_['to_node'], \
                                link_['to_orn'], \
                                link_['alignment'] \
                             ]
            fields = ["L"]
            fields.append(str(link_['from_node']))
            fields.append(str(link_['from_orn']))
            fields.append(str(link_['to_node']))
            fields.append(str(link_['to_orn']))

            if fv.is_gfa1_cigar(link_['alignment']):
                fields.append(str(link_['alignment']))
            else:
                fields.append("*")
            if not link_['eid'] in(None, '*'):
                fields.append("ID:Z:" + str(link_['eid']))
            fields.extend(utils._serialize_opt_fields(link_dict))
        else:
            defined_fields = [ \
                                link_.from_node, \
                                link_.from_orn, \
                                link_.to_node, \
                                link_.to_orn, \
                                link_.alignment \
                             ]
            fields = ["L"]
            fields.append(str(link_.from_node))
            fields.append(str(link_.from_orn))
            fields.append(str(link_.to_node))
            fields.append(str(link_.to_orn))

            if fv.is_gfa1_cigar(link_.alignment):
                fields.append(str(link_.alignment))
            else:
                fields.append("*")
            
            if not link_.eid in(None, '*'):
                fields.append("ID:Z:" + str(link_.eid))               
            fields.extend(utils._serialize_opt_fields(link_.opt_fields))

        if not utils._are_fields_defined(defined_fields) or \
           not utils._check_fields(fields[1:], LINK_FIELDS):
            raise GFA1SerializationError()
            
        return str.join("\t", fields)

    except(KeyError, AttributeError, GFA1SerializationError) as e:
        serializer_logger.debug(utils._format_exception(identifier, e))
        return ""


################################################################################
# SUBGRAPH SERIALIZER
################################################################################
def point_to_node(gfa, node_id):
    """Check if the given node_id point to a node in the gfa graph.
    """
    return gfa.node(node_id) != None


def _serialize_subgraph_elements(subgraph_elements, gfa=None):
    """Serialize the elements belonging to a subgraph.

    Check if the orientation is provided for each element of the
    subgraph.

    If gfa is provided, each element can be tested wheter it
    is a node or another element of the GFA graph.
    Only nodes (segments) will be (and could be) serialized
    to elements of the Path.

    If a gfa graph is not provided there cannot be any control
    over nodes, and data will be process as is.

    :param subgraph: A Graph Element Subgraph.
    :param gfa: The GFA object that contain the subgraph.
    """
    elements = []
    for id, orientation in subgraph_elements.items():
        if gfa == None:
            if orientation != None:
                elements.append(str(id) + str(orientation))
        else:
            if orientation != None \
              and point_to_node(gfa, id):
                elements.append(str(id) + str(orientation))

    return str.join(",", elements)
   

def serialize_subgraph(subgraph_, identifier=DEFAULT_IDENTIFIER, gfa=None):
    """Serialize a Subgraph object or an equivalent dictionary.
    """
    identifier = utils._check_identifier(identifier)
    try:
        if isinstance(subgraph_, dict):
            subgraph_dict = copy.deepcopy(subgraph_)
            defined_fields = [\
                                subgraph_dict.pop('sub_id'), \
                                subgraph_dict.pop('elements') \
                             ]
            fields = ["P"]
            fields.append(subgraph_['sub_id'])
            fields.append(_serialize_subgraph_elements(subgraph_['elements'], gfa))

            if 'overlaps' in subgraph_:
                subgraph_dict.pop('overlaps')
                fields.append(str.join(",", subgraph_['overlaps'].value))
            else:
                fields.append("*")
            fields.extend(utils._serialize_opt_fields(subgraph_dict))
        else:
            defined_fields = [\
                                subgraph_.sub_id, \
                                subgraph_.elements \
                             ]
            opt_fields = copy.deepcopy(subgraph_.opt_fields)

            fields = ["P"]
            fields.append(subgraph_.sub_id)
            fields.append(_serialize_subgraph_elements(subgraph_.elements, gfa))
            if 'overlaps' in subgraph_.opt_fields:
                opt_fields.pop('overlaps')
                fields.append(str.join(",", subgraph_.opt_fields['overlaps'].value))
            else:
                fields.append("*")
            fields.extend(utils._serialize_opt_fields(opt_fields))

        if not utils._are_fields_defined(defined_fields) or \
           not utils._check_fields(fields[1:], PATH_FIELDS):
            raise GFA1SerializationError("Required fields missing or" \
                                        + " not valid.")
        return str.join("\t", fields)
            
    except(KeyError, AttributeError, GFA1SerializationError) as e:
        serializer_logger.debug(utils._format_exception(identifier, e))            
        return ""


################################################################################
# SERIALIZE GRAPH
################################################################################
def serialize_graph(graph, write_header=True):
    """Serialize a networkx.MulitDiGraph object.

    :param graph: A networkx.MultiDiGraph instance.
    :write_header: If set to True put a GFA1 header as first line.
    """
    if not isinstance(graph, nx.MultiDiGraph):
        raise ValueError("The object to serialize must be an instance " \
                        + "of a networkx.MultiDiGraph.")

    if write_header == True:
        string_serialize = "H\tVN:Z:1.0\n"

    for node_id, node in graph.nodes_iter(data=True):
        node_serialize = serialize_node(node, node_id)
        if len(node_serialize) > 0:
            string_serialize += node_serialize + "\n"

    for from_node, to_node, key in graph.edges_iter(keys=True):
        edge_serialize = serialize_edge(graph.edge[from_node][to_node][key], key)
        if len(edge_serialize) > 0:
            string_serialize += edge_serialize + "\n"
    return string_serialize


def serialize_gfa(gfa):
    """Serialize a GFA object into a GFA1 file.
    """
    gfa_serialize = serialize_graph(gfa._graph, write_header=True)
    for sub_id, subgraph in gfa.subgraphs().items():
        subgraph_serialize = serialize_subgraph(subgraph, sub_id, gfa)
        if len(subgraph_serialize) > 0:
            gfa_serialize += subgraph_serialize + "\n"
    return gfa_serialize


if __name__ == '__main__': # pragma: no cover
    pass
