from parser import line, error, field_validator as fv
import re

class Link (line.Line):

    def __init__ (self):
        super().__init__ ('L')
    
    REQUIRED_FIELDS = { \
    'from' : fv.GFA1_NAME, \
    'from_orn' : fv.GFA1_ORIENTATION, \
    'to': fv.GFA1_NAME, \
    'to_orn' : fv.GFA1_ORIENTATION, \
    'overlap' : fv.GFA1_CIGAR \
    }

    PREDEFINED_OPTFIELDS = { \
    'MQ' : fv.TYPE_i, \
    'NM' : fv.TYPE_i, \
    'RC' : fv.TYPE_i, \
    'FC' : fv.TYPE_i, \
    'KC' : fv.TYPE_i, \
    'ID' : fv.TYPE_Z \
    }

    @classmethod
    def from_string (cls, string):
        """!
        Extract the link fields from the string.
        The string can contain the L character at the begin or can only contains the fields
        of the link directly.
        """
        fields = re.split ('\t', string)
        lfields = []
        if fields[0] == 'L':
            fields = fields[1:]
            
        link = Link ()

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

        return link
