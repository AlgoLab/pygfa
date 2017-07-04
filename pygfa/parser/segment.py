from parser import line, error, field_validator as fv
import re

def is_segmentv1 (line_repr):
    """Checks wether a given string or line belongs to a Segment of the first GFA version.
    @param string A string or a Line that is supposed to represent an S line.
    @exceptions Exception Launch a generic exception if the given parameter is
    not a string."""
    try:
        if isinstance (line_repr, str):        
            fields = re.split("\t", line_repr)
            if re.fullmatch (fv.DATASTRING_VALIDATION_REGEXP[fv.GFA1_SEQUENCE], \
                                 fields[2]) and \
                                 fields[0] == 'S':
                                 return True
        else:
            return line_repr.type == 'S' and line_repr.fields['name'] != None
        
    except: pass
    return False

def is_segmentv2 (line_repr):
    """Checks wether a given string or line belongs to a Segment of the second GFA version.
    @param string A string or a Line that is supposed to represent an S line.
    @exceptions Exception Launch a generic exception if the given parameter is
    not a string."""
    try:
        if isinstance (line_repr, str):        
            fields = re.split("\t", line_repr)
            if re.fullmatch (fv.DATASTRING_VALIDATION_REGEXP[fv.GFA2_POSITION], \
                                 fields[2]) and \
                                 fields[0] == 'S':
                                 return True
        else:
            return line_repr.type == 'S' and line_repr.fields['sid'] != None
        
    except: pass
    return False

class SegmentV1 (line.Line):

    def __init__ (self):
        super().__init__ ('S')
    
    REQUIRED_FIELDS = { \
    'name' : fv.GFA1_NAME, \
    'sequence' : fv.GFA1_SEQUENCE \
    }

    PREDEFINED_OPTFIELDS = { \
    'LN' : fv.TYPE_i, \
    'RC' : fv.TYPE_i, \
    'FC' : fv.TYPE_i, \
    'KC' : fv.TYPE_i, \
    'SH' : fv.HEX_BYTE_ARRAY, \
    'UR' : fv.TYPE_Z \
    }

    @classmethod
    def from_string (cls, string):
        """Extract the segment fields from the string.
        The string can contain the S character at the begin or can only contains the fields
        of the segment directly."""
        fields = re.split ('\t', string)
        sfields = []
        if fields[0] == 'S':
            fields = fields[1:]
            
        segment = SegmentV1 ()

        # the required fields are in the first two columns
        name_f = fv.validate (fields[0], cls.REQUIRED_FIELDS['name'])
        sfields.append (line.Field ('name', name_f))

        seq_f = fv.validate (fields[1], cls.REQUIRED_FIELDS['sequence'])
        sfields.append (line.Field ('sequence', seq_f))

        for field in fields[2:]:
            sfields.append (line.OptField.from_string (field))
            
        for field in sfields:
            segment.add_field (field)

        return segment


class SegmentV2 (line.Line):

    def __init__ (self):
        super().__init__ ('S')
    
    REQUIRED_FIELDS = { \
    'sid' : fv.GFA2_ID, \
    'slen' : fv.GFA2_INT, \
    'sequence' : fv.GFA2_SEQUENCE \
    }

    @classmethod
    def from_string (cls, string):
        """Extract the segment fields from the string.
        The string can contain the S character at the begin or can only contains the fields
        of the segment directly."""
        fields = re.split ('\t', string)
        sfields = []
        if fields[0] == 'S':
            fields = fields[1:]
            
        segment = SegmentV2 ()

        sid_f = fv.validate (fields[0], cls.REQUIRED_FIELDS['sid'])
        sfields.append (line.Field ('sid', sid_f))

        slen_f = fv.validate (fields[1], cls.REQUIRED_FIELDS['slen'])
        sfields.append (line.Field ('slen', slen_f))

        sequence_f = fv.validate (fields[2], cls.REQUIRED_FIELDS['sequence'])
        sfields.append (line.Field ('sequence', sequence_f))
        
        for field in fields[3:]:
            sfields.append (line.OptField.from_string (field))
            
        for field in sfields:
            segment.add_field (field)

        return segment
