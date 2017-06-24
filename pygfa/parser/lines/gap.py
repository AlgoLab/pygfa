from parser import line, error, field_validator as fv
import re

class Gap (line.Line):

    def __init__ (self):
        super().__init__ ('G')
    
    REQUIRED_FIELDS = { \
    'gid' : 'oid', \
    'sid1' : 'ref', \
    'sid2' : 'ref', \
    'distance' : 'int', \
    'variance' : 'oint' \
    }

    @classmethod
    def from_string (cls, string):
        """Extract the Gap fields from the string.
        The string can contain the G character at the begin or can only contains the fields
        of the Gap directly."""
        fields = re.split ('\t', string)
        gfields = []
        if fields[0] == 'G':
            fields = fields[1:]
            
        gap = Gap ()

        gid_f = fv.validate (fields[0], cls.REQUIRED_FIELDS['gid'])
        gfields.append (line.Field ('gid', gid_f))

        sid1_f = fv.validate (fields[1], cls.REQUIRED_FIELDS['sid1'])
        gfields.append (line.Field ('sid1', sid1_f))

        sid2_f = fv.validate (fields[2], cls.REQUIRED_FIELDS['sid2'])
        gfields.append (line.Field ('sid2', sid2_f))

        disp_f = fv.validate (fields[3], cls.REQUIRED_FIELDS['distance'])
        gfields.append (line.Field ('distance', disp_f))
        
        variance_f = fv.validate (fields[4], cls.REQUIRED_FIELDS['variance'])
        gfields.append (line.Field ('variance', variance_f))
        
        for field in fields[5:]:
            gfields.append (line.OptField.from_string (field))
            
        for field in gfields:
            gap.add_field (field)

        return gap


