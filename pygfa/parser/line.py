from parser import error, field_validator as fv
import re

# support for duck typing
def is_field (field):
    """! A field is valid if it has at least a name and a value attribute/property."""
    for attr in ('_name', '_value'):
        if not hasattr (field, attr):
            return False
    if field.name == None or field.value == None:
        return False
    if not isinstance (field.name, str):
        return False
    return True


def is_optfield (field):
    """!
    A field is an optfield if it's a field with name that match a given expression
    and its type is defined
    """
    return is_field (field) and \
      re.fullmatch ('[A-Za-z0-9]' * 2, field.name) and \
      hasattr (field, '_type') and \
      field.type != None


      

class Line:
    """!
    A generic Line, it's unlikely that it will be directly instantiated (but could be done so).
    Their sublcass should be used instead.
    One could instatiate a Line to save a custom line in his gfa file.
    """
    REQUIRED_FIELDS = {}
    PREDEFINED_OPTFIELDS = {} # this will contain tha name of the required optfield for
        # each kind of line and the ralative type of value the value of the field must contains

    
    def __init__ (self, line_type = None):
        self._fields = {}
        self._type = line_type


    def is_valid (self):
        """!
        Check if the line is valid.
        Defining the method here allows to have automatically validated all the line of the
        specifications.
        """
        for required_field in self.REQUIRED_FIELDS:
            if not required_field in self.fields:
                return False
        return True

        
    @classmethod
    def get_static_fields (cls):
        keys = []
        values = []
        for key, value in cls.REQUIRED_FIELDS.items ():
            keys.append (key)
            values.append (value)

        for key, value in cls.PREDEFINED_OPTFIELDS.items ():
            keys.append (key)
            values.append (value)
        return dict (zip (keys, values))


    @property
    def type (self):
        return self._type


    @property
    def fields (self):
        return self._fields
        
    
    def add_field (self, field):
        """!
        @param field The field to add to the line
        
        @exceptions InvalidFieldError If a 'name' and a 'value' attributes are not found or
        the field has already been added
        """
        if not (is_field (field) or is_optfield (field)):
            raise  error.InvalidFieldError ("A valid field must be attached")

        if field.name in self.fields:
            raise error.InvalidFieldError ("This field is already been added, field name: '{0}'.".format (field.name))

        if field.name in self.REQUIRED_FIELDS:
            self._fields[field.name] = field
        else: # here we are appending an optfield
              if not is_optfield (field):
                  raise error.InvalidFieldError ("The field given it's not a valid optfield nor a required field.")

              self._fields[field.name] = field

        return True
    
    def remove_field (self, field):
        """!
        If the field is contained in the line it gets removed.
        Othrewise it does nothing without raising exceptions.
        """
        field_name = field
        if is_field (field):
            field_name = field.name
        
        if field_name in self.fields:
            self.fields.pop (field_name)
        

    
    @classmethod
    def from_string (cls, string):
        raise NotImplementedError

    
    def __str__ (self):
        tmp_str = "line_type: {0}, fields: [".format (str (self.type))
        field_strings = []
        
        for field in self.fields:
            field_strings.append( str (field))
        
        tmp_str += str.join (", ", field_strings) + "]"
        return tmp_str



    
            
class Field:
    """!
    This class represent any required field.
    The type of field is bound to the field name.
    """
    def __init__ (self, name, value):
        self._name = name
        self._value = value

    @property
    def name (self):
        return self._name

    @property
    def value (self):
        return self._value

    
    def __eq__ (self, other):
        if isinstance (other, self.__class__):
            return self.name == other.name and \
              self.value == other.value

        return NotImplemented

    def __neq__ (self, other):
        return not self ==  other

    def __str__ (self):
        return str.join (":", (self.name, str (self.value)))

    
    

class OptField(Field):

    def __init__ (self, name, value, field_type):
        if not re.fullmatch ('[A-Za-z0-9]' * 2, name):
            raise ValueError ("Invalid optfield name, given '{0}'".format (name))

        if not re.fullmatch ("^[ABHJZif]$", field_type):
            raise ValueError ("Invalid type for an optional field.")
        
        self._name = name
        self._type = field_type
        self._value = fv.validate (value, field_type)
    

    @property
    def type (self):
        return self._type


    @classmethod
    def from_string (cls, string):
        """!
        Create an OptField with a given string that respects the form
        TAG:TYPE:VALUE, where:
        TAG match [A-Za-z0-9][A-Za-z0-9]
        TYPE match [AiZfJHB]
        """
        groups = re.split (":", string.strip ())
        if len (groups) != 3:
            raise ValueError ("OptField must have a name, a type and a value, given{0}".format (string) )

        optfield = OptField (groups[0], groups[2], groups[1])
        return optfield
    
    
    def __eq__ (self, other):
        try:
            return self.name == other.name and \
              self.value == other.value and \
              self.type == other.type

        except: return False

    
    def __neq__ (self, other):
        return not self == other;

    
    def __str__ (self):
        return str.join (":", (self.name, self.type, str (self.value)))
