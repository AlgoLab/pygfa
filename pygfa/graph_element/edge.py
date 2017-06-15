from parser.lines import edge, fragment, containment, gap
from parser import line
import copy

class InvalidEdgeError: pass

def is_edge (object):
    try:
        return \
          hasattr (object, '_eid') and \
          object._from_node != None and \
          object._to_node != None and \
          hasattr (object, '_from_positions') and \
          hasattr (object, '_to_positions') and \
          hasattr(object, '_alignment')
    except: return False

class Edge:

    def __init__ (self, edge_id, from_node, to_node, from_positions, to_positions, alignment, displacement = None, variance=None, opt_fields={}):

        if not (isinstance (from_positions, tuple) and len (from_positions) == 2):
            raise Exception ("Ivalid from_node tuple: given: {0}".format (str (from_positions)))

        if not (isinstance (to_positions, tuple) and len (to_positions) == 2):
            raise Exception ("Ivalid to_position tuple: given: {0}".format (str (to_position)))

        self._eid = edge_id
        self._from_node = from_node
        self._to_node = to_node
        self._from_positions = from_positions
        self._to_positions = to_positions
        self._alignment = alignment

        self._displacement = displacement
        self._variance = variance

        self._opt_fields = {}
        for key, field in opt_fields.items ():
            if line.is_field (field):
                self._opt_fields[key] = copy.deepcopy (field)
        
        
    @property
    def eid (self):
        return self._eid

    @property
    def from_node (self):
        return self._from_node

    @property
    def to_node (self):
        return self._to_node

    @property
    def from_positions (self):
        return self._from_positions

    @property
    def to_positions (self):
        return self._to_positions
    
    @property
    def alignment (self):
        return self._alignment

    @property
    def displacement (self):
        return self._displacement

    @property
    def variance (self):
        return self._variance
    
    @property
    def opt_fields (self):
        return self._opt_fields

    
    @classmethod
    def from_line (cls, line):
        try:
            fields = copy.deepcopy (line.fields)
            if line.type == 'L':
                if 'ID' in line.fields:
                    fields.pop('ID')
                fields.pop ('from')
                fields.pop ('from_orn')
                fields.pop ('to')
                fields.pop ('to_orn')
                fields.pop ('overlap')
                    
                return Edge ( \
                    '*' if 'ID' not in line.fields else line.fields['ID'].value, \
                    line.fields['from'].value + line.fields['from_orn'].value, \
                    line.fields['to'].value + line.fields['to_orn'].value, \
                    (None, None), \
                    (None, None), \
                    line.fields['overlap'].value, \
                    opt_fields = fields)

            if line.type == 'C':
                if 'ID' in line.fields:
                    fields.pop('ID')
                fields.pop ('from')
                fields.pop ('from_orn')
                fields.pop ('to')
                fields.pop ('to_orn')
                fields.pop ('overlap')
                return Edge ( \
                    '*' if 'ID' not in line.fields else line.fields['ID'].value, \
                    line.fields['from'].value + line.fields['from_orn'].value, \
                    line.fields['to'].value + line.fields['to_orn'].value, \
                    (None, None), \
                    (None, None), \
                    line.fields['overlap'].value,\
                    opt_fields = fields)

            if line.type == 'F':
                fields.pop ('sid')
                fields.pop ('external')
                fields.pop ('sbeg')
                fields.pop ('send')
                fields.pop ('fbeg')
                fields.pop ('fend')
                fields.pop ('alignment')
                return Edge ( \
                    None, \
                    line.fields['sid'].value, \
                    line.fields['external'].value, \
                    (line.fields['sbeg'].value, line.fields['send'].value), \
                    (line.fields['fbeg'].value, line.fields['fend'].value), \
                    line.fields['alignment'].value, \
                    opt_fields = fields)

            if line.type == 'E':
                fields.pop ('eid')
                fields.pop ('sid1')
                fields.pop ('sid2')
                fields.pop ('beg1')
                fields.pop ('end1')
                fields.pop ('beg2')
                fields.pop ('end2')
                fields.pop ('alignment')                

                return Edge ( \
                    line.fields['eid'].value, \
                    line.fields['sid1'].value, \
                    line.fields['sid2'].value, \
                    (line.fields['beg1'].value, line.fields['end1'].value), \
                    (line.fields['beg2'].value, line.fields['end2'].value), \
                    line.fields['alignment'].value, \
                    opt_fields = fields)

            if line.type == 'G':
                fields.pop ('gid')
                fields.pop ('sid1')
                fields.pop ('sid2')
                fields.pop ('displacement')
                fields.pop ('variance')
                
                return Edge ( \
                    line.fields['gid'].value, \
                    line.fields['sid1'].value, \
                    line.fields['sid2'].value, \
                    (None, None), \
                    (None, None), \
                    None, \
                    line.fields['displacement'].value, \
                    line.fields['variance'].value, \
                    opt_fields = fields)

        except Exception as e:
            raise e


    def __eq__ (self, other):
        try:

            if self.eid != other.eid or \
              self.from_node != other.from_node or \
              self.to_node != other.to_node or \
              self.from_positions != other.from_positions or \
              self.to_positions != other.to_positions or \
              self.alignment != other.alignment or \
              self.displacement != other.displacement or \
              self.variance != other.variance:
                return False

            for key, field in self.opt_fields.items ():
                if not key in other.opt_fields or \
                  self.opt_fields[key] != other.opt_fields[key]:
                  return False

        except: return False
        return True

    # TODO: complete me
    def __str__ (self):
        string = "eid: " + self.eid
        return string
