import re
from parser import error


DATASTRING_VALIDATION_REGEXP = \
  {\
  'A' : "^[!-~]", # any printable character \
  'i' : "^[-+]?[0-9]+$", # Signed integer \
  'f' : "^[-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?$", # Single-precision floating number \
  'Z' : "^[ !-~]+$", # Printable string, including space \
  'J' : "^[ !-~]+$",  # JSON, excluding new-line and tab characters \
  'H' : "^[0-9A-F]+$", # Byte array in the Hex format \
  'B' : "^[cCsSiIf](,[-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?)+$", # Integer or numeric array \
  'lbl' : "^[!-)+-<>-~][!-~]*$", # segment/path label (segment name) \
  'orn' : "^\+|-$", #segment orientation \
  'lbs' : "^[!-)+-<>-~][!-~]*[+-](,[!-)+-<>-~][!-~]*[+-])+$", # multiple labels with orientations, comma-sep \
  'seq' : "^\*$|^[A-Za-z=.]+$", # nucleotide sequence (segment sequence) \
  'pos' : "^[0-9]*$", # positive integer \
  'cig' : "^(\*|(([0-9]+[MIDNSHPX=])+))$", # CIGAR string \
  'cgs' : "^(\*|(([0-9]+[MIDNSHPX=])+))(,(\*|(([0-9]+[MIDNSHPX=])+)))*$", # multiple CIGARs, comma-sep \
  'cig2' : "^([0-9]+[MDIP])+$", #CIGAR string for GFA2 \
  'cmt' : ".*" # content of comment line, everything is allowed \
  }

def is_valid (string, datatype):
    """
    Checks if the string respect the datatype.
    @param datatype The type of data corresponding to the string
    @param fieldname The fieldname to use in the error message"""
    if not isinstance (string, str):
        raise error.FormatError ("A string must be given to validate it, given:{0}".format (string))
    if not datatype in DATASTRING_VALIDATION_REGEXP:
        raise error.UnknownDataTypeError (\
                                        "Invalid field datatype," + \
                                        "given: {0}".format (datatype) \
                                        )
                                        
    regexp = DATASTRING_VALIDATION_REGEXP[datatype]
    if not re.fullmatch(regexp, string): # moved from match to fullmatch, see if this makes any problems (as of now it doesn't)
        return False

    return True


def validate (string, datatype):
    """Return the value with the type closer to the one it's represented."""
    if not is_valid (string, datatype):
        raise error.InvalidFieldError ("The string cannot be validated within its datatype,\n" + \
                             "given string : {0}\ndatatype: {1}.".format (string, datatype))

    if datatype in ('i'):
        return int (string)
    elif datatype in ('pos'):
        position = int (string)
        if position < 0:
            raise Exception ("Position must be >= 0.")
        return position
    
    elif datatype in ('f'):
        return float (string)
    elif datatype in ('orn', 'A', 'Z', 'seq', 'lbl', 'cig', 'H', 'B'): #TODO?: for lbl check for path correctness
        return string
    elif datatype in ('lbs', 'cgs'):
        return string.split(",")
    elif datatype in ('J'):
        return string # TODO: ask if the json must be manipulated
    else:
        raise error.UnknownDataTypeError ("Datatype to be validated not found.")
