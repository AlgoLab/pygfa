import re
from parser import error


"""These are the type of value a field can assume, the tag is treated differently.
These are the same as the ones in rgfa, I've extended the list to support GFA2.
GFA2: 'id', 'ids', 'ref', 'rfs', 'cig2', 'opt_id', 'trc', 'aln', 'pos2', 'seq2', 'int'"""
DATASTRING_VALIDATION_REGEXP = \
  {\
  'A' : "^[!-~]", # any printable character \
  'i' : "^[-+]?[0-9]+$", # Signed integer \
  'f' : "^[-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?$", # Single-precision floating number \
  'Z' : "^[ !-~]+$", # Printable string, including space \
  'J' : "^[ !-~]+$",  # JSON, excluding new-line and tab characters \
  'H' : "^[0-9A-F]+$", # Byte array in the Hex format \
  'B' : "^[cCsSiIf](,[-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?)+$", # Integer or numeric array \
  'id' : "^[!-~]+$", # it's the lbl for GFA2 \
  'ids' : "^[!-~]+([ ][!-~]+)*$", # it's the lbs for GFA2 \
  'lbl' : "^[!-)+-<>-~][!-~]*$", # segment/path label (segment name) \
  'ref' : "^[!-~]+[+-]$", \
  'rfs' : "^[!-~]+[+-]([ ][!-~]+[+-])*$", # array of references \
  'orn' : "^\+|-$", #segment orientation \
  'lbs' : "^[!-)+-<>-~][!-~]*[+-](,[!-)+-<>-~][!-~]*[+-])+$", # multiple labels with orientations, comma-sep \
  'seq' : "^\*$|^[A-Za-z=.]+$", # nucleotide sequence (segment sequence) \
  'pos' : "^[0-9]*$", # positive integer \
  'cig' : "^(\*|(([0-9]+[MIDNSHPX=])+))$", # CIGAR string \
  'cgs' : "^(\*|(([0-9]+[MIDNSHPX=])+))(,(\*|(([0-9]+[MIDNSHPX=])+)))*$", # multiple CIGARs, comma-sep \
  'cmt' : ".*", # content of comment line, everything is allowed \
  'int' : "^[0-9]+$", # GFA1 has pos to describe any positive integer, but pos accept the empty string, while 'int' doesn't \
  'trc' : "^[0-9]+(,[0-9]+)*$", \
  'aln' : "^\*$|^[0-9]+(,[0-9]+)*$|^([0-9]+[MDIP])+$", \
  'pos2' : "^[0-9]+\$?$", # pos2 represent a position in GFA2, it's similar in NO WAY to pos which represent a positive integer in GFA1
  'cig2' : "^([0-9]+[MDIP])+$", # CIGAR string for GFA2 \
  'seq2' : "^\*$|^[!-~]+$", # seq2 is a GFA2 sequence, it's more flexible than GFA1 seq \ 
  'opt_id' : "^\*$|^[!-~]+$" # optional id  for GFA2 \
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
    elif datatype in ('pos', 'int'):
        # fullmatch grants that we have a string whose int value is >= 0
        
        # position = int (string)
        # if position < 0:
        #     raise Exception ("Position must be >= 0.")
        return int (string)
    
    elif datatype in ('f'):
        return float (string)

    elif datatype in ('lbs', 'cgs'):
        return string.split(",")
    elif datatype in ('aln'): # string is either * or trace or a cigar
        if string == "*":
            return string
        elif is_valid (string, 'cig2'):
            return validate (string, 'cig2')
        else:
            return validate (string, 'trc')
            
    elif datatype in ('J'):
        return string # TODO: ask if the json must be manipulated
    elif datatype in ('ids', 'rfs'):
        return string.split ()
        

    else: # ('orn', 'A', 'Z', 'seq', 'lbl', 'cig', 'cig2', 'H', 'B', 'trc', 'id', 'ref', pos2', 'seq2') #TODO?: for lbl check for path correctness
        return string
