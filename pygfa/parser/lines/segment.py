from parser import line, error, field_validator as fv
import re

class Segment (line.Line):

    def __init__ (self):
        super().__init__ ('S')
    
    REQUIRED_FIELDS = { \
    'name' : 'lbl', \
    'seq' : 'seq' \
    }

    PREDEFINED_OPTFIELDS = { \
    'LN' : 'i', \
    'RC' : 'i', \
    'FC' : 'i', \
    'KC' : 'i', \
    'SH' : 'H', \
    'UR' : 'Z' \
    }

    @classmethod
    def from_string (cls, string):
        """Extract the segment fields from the string.
        The string can contain the S character at the begin or can only contains the fields
        of the segment directly."""
        fields = re.split ('\t', string)
        sfields = []
        if fields[0] == 'S':
            fields = fields[1:] #skip the first field (the H)
            
        segment = Segment ()

        # the required fields are in the first two columns
        name_f = fv.validate (fields[0], cls.REQUIRED_FIELDS['name'])
        sfields.append (line.Field ('name', name_f))

        seq_f = fv.validate (fields[1], cls.REQUIRED_FIELDS['seq'])
        sfields.append (line.Field ('seq', seq_f))

        for field in fields[2:]:
            sfields.append (line.OptField.from_string (field))
            
        for field in sfields:
            segment.add_field (field)
        # header._fields.extend (sfields)
        return segment
        

