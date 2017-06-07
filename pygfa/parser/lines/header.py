from parser import line, error, field_validator as fv
import re

class Header(line.Line):

    PREDEFINED_OPTFIELDS = \
      { \
            'VN' : 'Z', \
            'TS' : 'i' \
      }
                                
    
    
    def __init__ (self):
        super().__init__ ('H')
        self.PREDEFINED_OPTFIELDS['VN'] = 'Z'
        self.PREDEFINED_OPTFIELDS['TS'] = 'i'


    @classmethod
    def from_string (cls, string):
        """Extract the header fields from the string.
        The string can contain the H character at the begin or can only contains the fields
        of the header directly."""
        fields = re.split ('\t', string)
        hfields = []
        if fields[0] == 'H':
            fields = fields[1:] #skip the first field (the H)
            
        header = Header ()

        for field in fields:
            hfields.append (line.OptField.from_string (field))

        for field in hfields:
            header.add_field (field)
#        header._fields.extend (hfields)

        return header
        