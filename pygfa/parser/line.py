from parser import error, field_validator as fv
import re

# support for duck typing
def is_field (field):
    """A field is valid if it has at least a name and a value attribute/property."""
    for attr in ('_name', '_value'):
        if not hasattr (field, attr):
            return False
    if field.name == None or field.value == None:
        return False
    if not isinstance (field.name, str):
        return False
    return True


def is_optfield (field):
    """A field is an optfield if it's a field with name that match a given expression
    and its type is defined"""
    return is_field (field) and \
      re.fullmatch ('[A-Za-z0-9]' * 2, field.name) and \
      hasattr (field, '_type') and \
      field.type != None


      

class Line:
    """A generic Line, it's unlikely that it will be directly instantiated (but could be done so).
    Their sublcass should be used instead.
    One could instatiated a Line to save a custom line in his gfa file."""
    REQUIRED_FIELDS = {}
    PREDEFINED_OPTFIELDS = {} # this will contain tha name of the required optfield for
        # each kind of line and the ralative type of value the value of the field must contains

    
    def __init__ (self, line_type = None):
        self._fields = {}
        self._type = line_type
        
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
        """
        @param field The field to add to the line
        @raise InvalidFieldError If a 'name' and a 'value' attributes are not found or
        the field has already been added"""
        if not is_field (field):
            raise  error.InvalidFieldError ("A valid field must be attached")

        if field.name in self.fields:
            raise error.InvalidFieldError ("This field is already been added, field name: '{0}'.".format (field.name))

        # cast to string for type compatibility with validation methods.
        # for field whose value is a list, cast to a comma separated string with values
        field_value = ""
        if isinstance (field.value, list):
            field_value = str.join(",", field.value)
        else:
            field_value = str (field.value)
            
        static_fields = self.get_static_fields ()
        if field.name in static_fields:
            field_type = static_fields[field.name]
            if fv.is_valid (field_value, field_type):
              validated_value = fv.validate (field_value, field_type)
              self._fields[field.name] = Field (field.name, validated_value)
            else:
                raise error.InvalidFieldError ("Value must respect its type, given {0}, expected {1}".format (field.value, field_type))
        else: # here we are appending an optfield
            
              if not is_optfield (field):
                  raise error.InvalidFieldError ("The field given it's not a valid optfield nor a required field.")

              if fv.is_valid (field_value, field.type):
                  self._fields[field.name] = OptField (field.name, field_value, field.type)
              else:
                  raise error.InvalidFieldError (\
                                                    "Value must respect its type, " + \
                                                    "string given: {0}\n".format (field.value) + \
                                                    "of type: {0}".format (field.type))
        return True
    

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
    """This class represent any required field.
    The type of field is bound to the field name.
    TODO: choose to add all the field name in the validator module so that it's
    possible to validate the value of the field here."""
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
            raise Exception ("Invalid optfield name, given".format (name))

        if not re.fullmatch ("^[ABHJZif]$", field_type):
            raise Exception ("Invalid type for an optional field.")
        
        self._name = name
        self._type = field_type
        self._value = fv.validate (value, field_type)
    

    @property
    def type (self):
        return self._type


    @classmethod
    def from_string (cls, string):
        """Create an OptField with a given string that respects the form
        TAG:TYPE:VALUE, where:
        TAG match [A-Za-z0-9][A-Za-z0-9]
        TYPE match [AiZfJHB]"""
        groups = re.split (":", string.strip ())
        if len (groups) != 3:
            raise Exception ("OptField must have a name, a type and a value, given".format (string) )

        optfield = OptField (groups[0], groups[2], groups[1])
        return optfield
    
    
    def __eq__ (self, other):
        if isinstance (other, self.__class__):
            return self.name == other.name and \
              self.value == other.value and \
              self.type == other.type

        return NotImplemented

    
    def __neq__ (self, other):
        return not self == other;

    
    def __str__ (self):
        return str.join (":", (self.name, self.type, str (self.value)))
