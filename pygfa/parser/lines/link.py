from parser import line, error, field_validator as fv
import re

class Link (line.Line):

    def __init__ (self):
        super().__init__ ('L')
    
    REQUIRED_FIELDS = { \
    'from' : 'lbl', \
    'from_orn' : 'orn', \
    'to': 'lbl', \
    'to_orn' : 'orn', \
    'overlap' : 'cig' \
    }

    PREDEFINED_OPTFIELDS = { \
    'MQ' : 'i', \
    'NM' : 'i', \
    'RC' : 'i', \
    'FC' : 'i', \
    'KC' : 'i', \
    'ID' : 'Z' \
    }

    @classmethod
    def from_string (cls, string):
        """Extract the link fields from the string.
        The string can contain the S character at the begin or can only contains the fields
        of the link directly."""
        fields = re.split ('\t', string)
        lfields = []
        if fields[0] == 'L':
            fields = fields[1:] #skip the first field (the H)
            
        link = Link ()

        # the required fields are in the first two columns

        from_name = fv.validate (fields[0], cls.REQUIRED_FIELDS['from'])
        from_orn = fv.validate (fields[1], cls.REQUIRED_FIELDS['from_orn'])
        to_name = fv.validate (fields[2], cls.REQUIRED_FIELDS['to'])
        to_orn = fv.validate (fields[3], cls.REQUIRED_FIELDS['to_orn'])
        overlap = fv.validate (fields[4], cls.REQUIRED_FIELDS['overlap'])

        lfields.append (line.Field ('from', from_name))
        lfields.append (line.Field ('from_orn', from_orn))
        lfields.append (line.Field ('to', to_name))
        lfields.append (line.Field ('to_orn', to_orn))
        lfields.append (line.Field ('overlap', overlap))

        for field in fields[5:]:
            lfields.append (line.OptField.from_string (field))
            
        for field in lfields:
            link.add_field (field)
        # header._fields.extend (sfields)
        return link
