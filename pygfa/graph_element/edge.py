import copy

from pygfa.graph_element.parser import edge, fragment, containment, gap
from pygfa.graph_element.parser import line

class InvalidEdgeError(Exception): pass

def is_edge (object):
    try:
        return \
          hasattr (object, '_eid') and \
          object._from_node != None and \
          object._to_node != None and \
          hasattr (object, '_from_positions') and \
          hasattr (object, '_from_orn') and \
          hasattr (object, '_to_positions') and \
          hasattr (object, '_to_orn') and \
          hasattr (object, '_alignment')
    except: return False

class Edge:

    def __init__ (self, \
                  edge_id, \
                  from_node, from_orn, \
                  to_node, to_orn, \
                  from_positions, \
                  to_positions, \
                  alignment, \
                  distance=None, \
                  variance=None, \
                  opt_fields={}):

        if not (isinstance (from_positions, tuple) and \
            len (from_positions) == 2):
            raise Exception ("Ivalid from_node tuple: given: {0}".format (\
                str (from_positions)))

        if not (isinstance (to_positions, tuple) and \
            len (to_positions) == 2):
            raise Exception ("Ivalid to_position tuple: given: {0}".format (\
                str (to_position)))

        self._eid = edge_id
        self._from_node = from_node
        self._from_orn = from_orn
        self._to_node = to_node
        self._to_orn = to_orn
        self._from_positions = from_positions
        self._to_positions = to_positions
        self._alignment = alignment

        self._distance = distance
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
    def from_orn (self):
        return self._from_orn

    @property
    def to_orn (self):
        return self._to_orn
    
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
    def distance (self):
        return self._distance

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
                    '*' if 'ID' not in line.fields else \
                        line.fields['ID'].value, \

                    line.fields['from'].value, \
                    line.fields['from_orn'].value, \
                    line.fields['to'].value, \
                    line.fields['to_orn'].value, \
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
                    '*' if 'ID' not in line.fields else \
                    line.fields['ID'].value, \

                    line.fields['from'].value, \
                    line.fields['from_orn'].value, \
                    line.fields['to'].value, \
                    line.fields['to_orn'].value, \
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
                    line.fields['sid'].value, None, \
                    line.fields['external'].value[0:-1], \
                    line.fields['external'].value[-1:], \
                    (line.fields['sbeg'].value, \
                        line.fields['send'].value), \
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
                    line.fields['sid1'].value[0:-1], \
                    line.fields['sid1'].value[-1:], \
                    line.fields['sid2'].value[0:-1], \
                    line.fields['sid2'].value[-1:], \
                    (line.fields['beg1'].value, line.fields['end1'].value), \
                    (line.fields['beg2'].value, line.fields['end2'].value), \
                    line.fields['alignment'].value, \
                    opt_fields = fields)

            if line.type == 'G':
                fields.pop ('gid')
                fields.pop ('sid1')
                fields.pop ('sid2')
                fields.pop ('distance')
                fields.pop ('variance')
                
                return Edge ( \
                    line.fields['gid'].value, \
                    line.fields['sid1'].value[0:-1], \
                    line.fields['sid1'].value[-1:], \
                    line.fields['sid2'].value[0:-1], \
                    line.fields['sid2'].value[-1:], \
                    (None, None), \
                    (None, None), \
                    None, \
                    line.fields['distance'].value, \
                    line.fields['variance'].value, \
                    opt_fields = fields)

        except Exception as e:
            raise e


    def __eq__ (self, other):
        try:

            if self.eid != other.eid or \
              self.from_node != other.from_node or \
              self.from_orn != other.from_orn or \
              self.to_node != other.to_node or \
              self.to_orn != other.to_orn or \
              self.from_positions != other.from_positions or \
              self.to_positions != other.to_positions or \
              self.alignment != other.alignment or \
              self.distance != other.distance or \
              self.variance != other.variance:
                return False

            for key, field in self.opt_fields.items ():
                if not key in other.opt_fields or \
                  self.opt_fields[key] != other.opt_fields[key]:
                  return False

        except: return False
        return True

    
    def __str__ (self):
        string = \
          "eid: " + str (self.eid) + ", " + \
          "from_node: " + str (self.from_node)  + ", " + \
          "from_orn: " + str (self.from_orn)  + ", " + \
          "to_node: " + str (self.to_node)  + ", " + \
          "to_orn: " + str (self.to_orn)  + ", " + \
          "from_positions: " + str (self.to_positions)  + ", " + \
          "alignment: " + str (self.alignment)  + ", " + \
          "distrance: " + str (self.distance)  + ", " + \
          "variance: " + str (self.variance)  + ", " + \
          "opt_fields: " + str (self.opt_fields)
        return string

if __name__ == '__main__':
    pass
