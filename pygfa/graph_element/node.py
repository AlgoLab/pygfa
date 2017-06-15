from parser.lines import segment
from parser import line
import copy

class InvalidNodeError (Exception): pass

def is_node (object):
    """Check wheter the given object is a graph_element object."""
    try:
        return object.nid != None and object.sequence != None and hasattr (object, '_slen')
    except: return False

class Node:

    def __init__ (self, node_id, sequence, length, opt_fields={}):
        if not isinstance (node_id, str) or node_id == '*':
            raise InvalidNodeError ("A Node has always a defined id of type string, " + \
                                 "given {0} of type {1}".format (node_id, type (node_id)))

        if not isinstance (sequence, str):
            raise Exception ("A sequence must be of type string, " + \
                                 "given {0} of type {1}".format (sequence, type (sequence)))

        if not ( \
                     (isinstance (length, int) and int (length) >= 0) or \
                     length == None \
                ):
            raise InvalidNodeError ("Sequence length must be a number >= 0, " + \
                                 "given {0} of type {1}".format (length, type (length)))
        self._nid = node_id
        self._sequence = sequence
        self._slen = length
        self._opt_fields = {}
        for key, field in opt_fields.items ():
            if line.is_field (field):
                self._opt_fields[key] = copy.deepcopy (field)
        
        
    @property
    def nid (self):
        return self._nid

    @property
    def sequence (self):
        return self._sequence

    @property
    def slen (self):
        return self._slen

    @property
    def opt_fields (self):
        return self._opt_fields
    
    @classmethod
    def from_line (cls, line):

        if not line.is_valid ():
            raise InvalidNodeError ("The line to be added must have all the required fields. Line type: '{0}'".format (line.type))
        
        try:
            fields = copy.deepcopy (line.fields)
            if line.type == 'S':
                if segment.is_segmentv1 (line):

                    fields.pop ('name')
                    fields.pop ('sequence')
                    # fields.remove_field ('LN') # LN field will be kept as optional field also
                    
                    return Node ( \
                            line.fields['name'].value, \
                            line.fields['sequence'].value, \
                            None if 'LN' not in line.fields else line.fields['LN'].value, \
                            fields)
                    
                else:
                    fields.pop ('sid')
                    fields.pop ('sequence')
                    fields.pop ('slen')                    

                    return Node ( \
                            line.fields['sid'].value, \
                            line.fields['sequence'].value, \
                            line.fields['slen'].value, \
                            fields)
                                
                
        except Exception as e:
            raise e

    def __eq__ (self, other):
        try:
            if self.nid != other.nid or \
              self.sequence != other.sequence or \
              self.slen != other.slen:
                return False
                
            for key, item in self.opt_fields.items ():
                if not key in other.opt_fields or \
                  not self.opt_fields[key] == other.opt_fields[key]:
                    return False
                    
        except: return False
        return True

    # TODO: change this
    def __str__ (self):
        string = "nid: " + str (self.nid)
        string += "\tsequence: " + str (self.sequence)
        string += "\tslen: " + str (self.slen)
        string += "\topt_fields: " + str.join ("\t", [str(field) for key, field in self.opt_fields.items()])
        return string
            
