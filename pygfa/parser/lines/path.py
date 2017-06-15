from parser import line, error, field_validator as fv
import re

class Path (line.Line):

    def __init__ (self):
        super().__init__ ('P')
    
    REQUIRED_FIELDS = { \
    'path_name' : 'lbl', \
    'seqs_names' : 'lbs', \
    'overlaps': 'cgs'
    }

    PREDEFINED_OPTFIELDS = {}

    @classmethod
    def from_string (cls, string):
        """Extract the path fields from the string.
        The string can contain the P character at the begin or can only contains the fields
        of the path directly."""
        fields = re.split ('\t', string) #add the strip
        pfields = []
        if fields[0] == 'P':
            fields = fields[1:] #skip the first field (the P)
            
        path = Path ()

        path_name = fv.validate (fields[0], cls.REQUIRED_FIELDS['path_name'])
        sequences_names = fv.validate (fields[1], cls.REQUIRED_FIELDS['seqs_names'])
        overlaps = fv.validate (fields[2], cls.REQUIRED_FIELDS['overlaps'])

        pfields.append (line.Field ('path_name', path_name))
        pfields.append (line.Field ('seqs_names', sequences_names))
        pfields.append (line.Field ('overlaps', overlaps))

        for field in fields[3:]:
            pfields.append (line.OptField.from_string (field))
            
        for field in pfields:
            path.add_field (field)
            
        return path
