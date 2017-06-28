from parser import line, field_validator as fv
from parser.lines import segment, edge, group, containment, path, fragment, link
from graph_element import edge as ge, node, subgraph
import copy, logging

# TODO: is this a good idea?
serializer_logger = logging.getLogger("gfa1_serializer")

################################################################################
# NODE SERIALIZER
################################################################################
def serialize_node (node):
    """!
    Serialize to the GFA1 specification a Graph Element Node or a
    dictionary that has the same informations.
    If the object cannot be serialized to GFA an empty string
    is returned.

    @param node A Graph Element Node or a dictionary
    """
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
            serializer_logger.debug (ke.print_exc ())
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
            serializer_logger.debug (ae.print_exc ())            
            return ""

################################################################################
# EDGE SERIALIZER
################################################################################

def serialize_edge (edge):
    """!
    Converts to a GFA1 line the given edge.
    Fragments and Gaps cannot be represented in GFA1 specification,
    so they are not serialized.

    # TODO explain better
    """
    if isinstance (edge, dict):
        try:
            if edge['eid'] == None: # edge is a fragment
                return ""
            elif edge['distance'] != None or \
              edge['variance'] != None: # edge is a gap
                return ""
            elif 'pos' in edge: # edge is a containment
                return _serialize_to_containment (edge)
            else:
                return _serialize_to_link (edge)
        except KeyError as ke:
            serializer_logger.debug (ke.print_exc ())
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
            serializer_logger.debug (ae.print_exc ())
            return ""

            
def _serialize_to_containment (containment):
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
            fields.append (str (containment['pos']))

            if fv.is_cigar1 (containment['alignment']):
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
            serializer_logger.debug (ke.print_exc ())            
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
            fields.append (str (containment.opt_fields['pos']))

            if fv.is_cigar1 (containment.alignment):
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
            serializer_logger.debug (ae.print_exc ())            
            return ""
        

def _serialize_to_link (link):
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

            if fv.is_cigar1 (link['alignment']):
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
            serializer_logger.debug (ke.print_exc ())            
            return ""
    else:
        try:
            fields = ["L"]

            fields.append (str (link.from_node))
            fields.append (str (link.from_orn))
            fields.append (str (link.to_node))
            fields.append (str (link.to_orn))

            if fv.is_cigar1 (link.alignment):
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
            serializer_logger.debug (ae.print_exc ())            
            return ""


################################################################################
# SUBGRAPH SERIALIZER
################################################################################
def serialize_subgraph (subgraph):
    """!
    """
    if isinstance (subgraph, dict):
        pass
    # TODO: complete me, but first refactor my graph element so that I can store
    # overlaps from PATHs

    
################################################################################
# OBJECT SERIALIZER
################################################################################
def serialize (object):
    if isinstance (object, dict):
        
        if 'nid' in object:
            return serialize_node (object)
        elif 'eid' in object:
            return serialize_edge (object)
        elif 'sub_id' in object:
            return "" # TODO: add serialize_subgraph here
    else:
        if hasattr (object, '_nid') or hasattr (object, 'nid'):
            return serialize_node (object)
        elif hasattr (object, '_eid') or hasattr (object, 'eid'):
            return serialize_edge (object)
        elif hasattr (object, '_sub_id') or hasattr (object, 'sub_nid'):
            return "" # TODO: add serialize_subgraph (object) here

    return "" # if it's not possible to serialize, return an empty string 
