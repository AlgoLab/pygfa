from parser import line, error, field_validator as fv
import re

class Containment (line.Line):

    def __init__ (self):
        super().__init__ ('C')
    
    REQUIRED_FIELDS = { \
    'from' : 'lbl', \
    'from_orn' : 'orn', \
    'to': 'lbl', \
    'to_orn' : 'orn', \
    'pos' : 'pos', \
    'overlap' : 'cig' \
    }

    PREDEFINED_OPTFIELDS = { \
    'NM' : 'i', \
    'RC' : 'i', \
    'ID' : 'Z' \
    }

    @classmethod
    def from_string (cls, string):
        """Extract the containment fields from the string.
        The string can contain the C character at the begin or can only contains the fields
        of the containment directly."""
        fields = re.split ('\t', string) #add the strip
        cfields = []
        if fields[0] == 'C':
            fields = fields[1:] #skip the first field (the C)
            
        containment = Containment ()

        from_name = fv.validate (fields[0], cls.REQUIRED_FIELDS['from'])
        from_orn = fv.validate (fields[1], cls.REQUIRED_FIELDS['from_orn'])
        to_name = fv.validate (fields[2], cls.REQUIRED_FIELDS['to'])
        to_orn = fv.validate (fields[3], cls.REQUIRED_FIELDS['to_orn'])
        pos = fv.validate (fields[4], cls.REQUIRED_FIELDS['pos'])
        overlap = fv.validate (fields[5], cls.REQUIRED_FIELDS['overlap'])

        cfields.append (line.Field ('from', from_name))
        cfields.append (line.Field ('from_orn', from_orn))
        cfields.append (line.Field ('to', to_name))
        cfields.append (line.Field ('to_orn', to_orn))
        cfields.append (line.Field ('pos', pos))
        cfields.append (line.Field ('overlap', overlap))

        for field in fields[6:]:
            cfields.append (line.OptField.from_string (field))
            
        for field in cfields:
            containment.add_field (field)
            
        return containment
