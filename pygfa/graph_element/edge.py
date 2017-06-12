from parser.lines import edge, fragment, containment, gap

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

    def __init__ (self, edge_id, from_node, to_node, from_positions, to_positions, alignment):

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

    
    @classmethod
    def from_line (cls, line):
        try:
            if line.type == 'L':
                return Edge ( \
                    '*' if 'ID' not in line.fields['ID'] else line.fields['ID'].value, \
                    line.fields['from'].value + line.field['from_orn'].value, \
                    line.fields['to'].value + line.field['to_orn'].value, \
                    (None, None), \
                    (None, None), \
                    line.fields['overlap'].value)

            if line.type == 'C':
                return Edge ( \
                    '*' if 'ID' not in line.fields['ID'] else line.fields['ID'].value, \
                    line.fields['from'].value + line.field['from_orn'].value, \
                    line.fields['to'].value + line.field['to_orn'].value, \
                    (None, None), \
                    (None, None), \
                    line.fields['overlap'].value)
                    # TODO: how to add pos field?

            if line.type == 'F':
                return Edge ( \
                    None, \
                    line.fields['sid'].value, \
                    line.fields['external'].value, \
                    (line.fields['sbeg'].value, line.fields['send'].value), \
                    (line.fields['fbeg'].value, line.fields['fend'].value), \
                    line.fields['alignment'].value)

            if line.type == 'E':
                 return Edge ( \
                    line.fields['eid'].value, \
                    line.fields['sid1'].value, \
                    line.fields['sid2'].value, \
                    (line.fields['beg1'].value, line.fields['end1'].value), \
                    (line.fields['beg2'].value, line.fields['end2'].value), \
                    line.fields['alignment'].value)

            if line.type == 'G':
                return Edge ( \
                    line.fields['gid'].value, \
                    line.fields['sid1'].value, \
                    line.fields['sid2'].value, \
                    (None, None), \
                    (None, None), \
                    None)
                    # TODO: add displacement and variance
                    

        except Exception as e:
            raise e
