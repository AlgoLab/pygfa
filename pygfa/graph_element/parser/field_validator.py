"""
Field validation module to check each field string against GFA1 specification.
"""

import re


class InvalidFieldError(Exception):
    """Exception raised when an invalid field is provided."""


class UnknownDataTypeError(Exception):
    """Exception raised when the datatype provided is not in
    the `DATASTRING_VALIDATION_REGEXP` dictionary.
    """


class FormatError(Exception):
    """Exception raised when a wrong type of object is given
    to the validator.
    """


TYPE_A = "A"
TYPE_i = "i"
TYPE_f = "f"
TYPE_Z = "Z"
JSON = "J"
HEX_BYTE_ARRAY = "H"
DEC_ARRAY = "B"

GFA1_NAME = "lbl"
GFA1_NAMES = "lbs"
GFA1_ORIENTATION = "orn"
GFA1_SEQUENCE = "seq"
GFA1_CIGAR = "cig"
GFA1_CIGARS = "cgs"
GFA1_INT = "pos"


# These are the types of value a field can assume.
# These are the same as the ones in rgfa.

DATASTRING_VALIDATION_REGEXP = {
    TYPE_A: "^[!-~]",
    # any printable character
    #
    TYPE_i: "^[-+]?[0-9]+$",
    # Signed integer
    #
    TYPE_f: r"^[-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?$",
    # Single-precision floating number
    #
    TYPE_Z: "^[ !-~]+$",
    # Printable string, including space
    #
    JSON: "^[ !-~]+$",
    # JSON, excluding new-line and tab characters
    #
    HEX_BYTE_ARRAY: "^[0-9A-F]+$",
    # Byte array in the Hex format
    #
    DEC_ARRAY: r"^[cCsSiIf](,[-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?)+$",
    # Integer or numeric array
    #
    GFA1_NAME: "^[!-)+-<>-~][!-~]*$",
    # segment/path label(segment name)
    #
    GFA1_ORIENTATION: r"^\+|-$",
    # segment orientation
    #
    ###
    #'lbs' : "^[!-)+-<>-~][!-~]*[+-](,[!-)+-<>-~][!-~]*[+-])+$",
    # multiple labels with orientations, comma-sep
    #
    # Changed according to issue 59, since the comma is accepted by [!-~],
    # it's not possible to make a clear regexp for an array of labels,
    # so the implementation has been modified to reflect
    # this behaviour, splitting the labels and checking them one by one
    # with the new lbs regexp beyond.
    #
    GFA1_NAMES: "^[!-)+-<>-~][!-~]*[+-]$",
    GFA1_SEQUENCE: r"^\*$|^[A-Za-z=.]+$",
    # nucleotide sequence(segment sequence)
    #
    GFA1_INT: "^[0-9]*$",
    # positive integer(CLAIM ISSUE HERE, MOVE TO -> int)
    #
    GFA1_CIGAR: r"^(\*|(([0-9]+[MIDNSHPX=])+))$",  # CIGAR string \
    GFA1_CIGARS: r"^(\*|(([0-9]+[MIDNSHPX=])+))(,(\*|(([0-9]+[MIDNSHPX=])+)))*$",
    # multiple CIGARs, comma-sep \
    #
    "cmt": ".*",
    # content of comment line, everything is allowed
    #
}


def is_valid(string, datatype):
    """Check if the string respects the datatype.

    :param datatype: The type of data corresponding to the string.
    :returns: True if the string respect the type defined by the datatype.
    :raises UnknownDataTypeError: If the datatype is not presents in
        `DATASTRING_VALIDATION_REGEXP`.
    :raises UnknownFormatError: If string is not python string.

    :TODO:
        Fix exception reference in the documentation.
    """
    if not isinstance(string, str):
        raise FormatError(f"A string must be given to validate it, given:{string}")
    if datatype not in DATASTRING_VALIDATION_REGEXP:
        raise UnknownDataTypeError(f"Invalid field datatype, given: {datatype}")
    regexp = DATASTRING_VALIDATION_REGEXP[datatype]
    if not re.fullmatch(regexp, string):
        return False
    return True


def is_gfa1_cigar(string):
    """Check if the given string is a valid CIGAR string
    as defined in the GFA1 specification.
    """
    return string != "*" and is_valid(string, GFA1_CIGAR)


def validate(string, datatype):
    """Return a value from the given string with the type closer to the
    one it's represented.
    """
    if not is_valid(string, datatype):
        raise InvalidFieldError(
            f"The string cannot be validated within its datatype,\ngiven string : {string}\ndatatype: {datatype}."
        )
    if datatype in (TYPE_i,):
        return int(string)
    elif datatype in (GFA1_INT,):
        # fullmatch grants that we have a string whose int value is >= 0

        # position = int(string)
        # if position < 0:
        #     raise Exception("Position must be >= 0.")
        return int(string)

    elif datatype in (TYPE_f,):
        return float(string)

    elif datatype in (GFA1_CIGARS,):
        return string.split(",")

    elif datatype in (JSON,):
        return string  # TODO: ask if the json must be manipulated
    else:
        # 'orn', 'A', 'Z', 'seq', 'lbl', 'cig', 'H', 'B', 'lbs'
        return string


if __name__ == "__main__":  # pragma: no cover
    pass
