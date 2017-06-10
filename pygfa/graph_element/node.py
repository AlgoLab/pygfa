from parser.lines import segment


class Node:

    def __init__ (self, node_id, sequence, length):
        if not isinstance (node_id, str):
            raise Exception ("A Node has always a defined id of type string, " + \
                                 "given {0} of type {1}".format (node_id, type (node_id)))

        if not isinstance (sequence, str):
            raise Exception ("A sequence must be of type string, " + \
                                 "given {0} of type {1}".format (sequence, type (sequence)))

        if not ( \
                     (isinstance (length, int) and int (length) >= 0) or \
                     length == None \
                ):
            raise Exception ("Sequence length must be a number >= 0, " + \
                                 "given {0} of type {1}".format (length, type (length)))
        self._nid = node_id
        self._sequence = sequence
        self._slen = length
        
    @property
    def nid (self):
        return self._nid

    @property
    def sequence (self):
        return self._sequence

    @property
    def slen (self):
        return self._slen

    @classmethod
    def from_line (cls, line):

        try:

            if line.type == 'S':
                if segment.is_segmentv1 (line):
                   
                    return Node ( \
                            line.fields['name'].value, \
                            line.fields['sequence'].value, \
                            None if 'LN' not in line.fields else line.fields['LN'].value)
                    
                else:

                    return Node ( \
                            line.fields['sid'].value, \
                            line.fields['sequence'].value, \
                            line.fields['slen'].value)
                                
                
        except Exception as e:
            raise e
