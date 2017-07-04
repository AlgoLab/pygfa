import re

from parser import line, field_validator as fv

class OGroup(line.Line):

    def __init__(self):
        super().__init__('O')
    
    REQUIRED_FIELDS = { \
    'oid' : fv.GFA2_OPTIONAL_ID, \
    'references' : fv.GFA2_REFERENCES \
    }

    @classmethod
    def from_string(cls, string):
        """Extract the OGroup fields from the string.

        The string can contains the O character at the begin or can only contains the fields
        of the OGroup directly.
        """
        fields = re.split('\t', string)
        ogfields = []
        if fields[0] == 'O':
            fields = fields[1:]
            
        ogroup = OGroup()

        oid_f = fv.validate(fields[0], cls.REQUIRED_FIELDS['oid'])
        ogfields.append(line.Field('oid', oid_f))

        references_f = fv.validate(fields[1], cls.REQUIRED_FIELDS['references'])
        ogfields.append(line.Field('references', references_f))

        for field in fields[2:]:
            ogfields.append(line.OptField.from_string(field))
            
        for field in ogfields:
            ogroup.add_field(field)
        
        return ogroup




class UGroup(line.Line):

    def __init__(self):
        super().__init__('U')
    
    REQUIRED_FIELDS = { \
    'uid' : fv.GFA2_OPTIONAL_ID, \
    'ids' : fv.GFA2_IDS \
    }

    @classmethod
    def from_string(cls, string):
        """Extract the UGroup fields from the string.
        
        The string can contains the U character at the begin or can
        only contains the fields of the UGroup directly.
        """
        fields = re.split('\t', string)
        ugfields = []
        if fields[0] == 'U':
            fields = fields[1:]
            
        ugroup = UGroup()

        uid_f = fv.validate(fields[0], cls.REQUIRED_FIELDS['uid'])
        ugfields.append(line.Field('uid', uid_f))

        references_f = fv.validate(fields[1], cls.REQUIRED_FIELDS['ids'])
        ugfields.append(line.Field('ids', references_f))

        for field in fields[2:]:
            ugfields.append(line.OptField.from_string(field))
            
        for field in ugfields:
            ugroup.add_field(field)
        
        return ugroup
