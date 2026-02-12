from __future__ import annotations

import re
from typing import TYPE_CHECKING, Dict

if TYPE_CHECKING:
    pass

from pygfa.graph_element.parser import field_validator as fv
from pygfa.graph_element.parser import line


def is_segmentv1(line_repr: str | line.Line) -> bool:
    """Check wether a given gfa line string probably belongs to a
    Segment of the first GFA version.

    :param line_repr: A string or a Line that is supposed to
        represent an S line.
    """
    try:
        if isinstance(line_repr, str):
            fields = re.split("\t", line_repr)
            if re.fullmatch(fv.DATASTRING_VALIDATION_REGEXP[fv.GFA1_SEQUENCE], fields[2]) and fields[0] == "S":
                return True
        else:
            return line_repr.type == "S" and line_repr.fields["name"] is not None

    except Exception:
        pass
    return False


class SegmentV1(line.Line):
    """A GFA1 Segment line."""

    def __init__(self):
        super().__init__("S")

    REQUIRED_FIELDS: Dict[str, str] = {"name": fv.GFA1_NAME, "sequence": fv.GFA1_SEQUENCE}

    PREDEFINED_OPTFIELDS: Dict[str, str] = {
        "LN": fv.TYPE_i,
        "RC": fv.TYPE_i,
        "FC": fv.TYPE_i,
        "KC": fv.TYPE_i,
        "SH": fv.HEX_BYTE_ARRAY,
        "UR": fv.TYPE_Z,
    }

    @classmethod
    def from_string(cls, string: str) -> SegmentV1:
        """Extract the segment fields from the string.

        The string can contains the S character at the begin
        or can only contains the fields of the segment directly.
        """
        if len(string.split()) == 0:
            raise line.InvalidLineError("Cannot parse the empty string.")
        fields = re.split("\t", string)
        sfields: list[line.Field | line.OptField] = []
        if fields[0] == "S":
            fields = fields[1:]

        if len(fields) < len(cls.REQUIRED_FIELDS):
            raise line.InvalidLineError("The minimum number of field for " + "SegmentV1 line is not reached.")
        segment = SegmentV1()
        name_f = fv.validate(fields[0], cls.REQUIRED_FIELDS["name"])
        sfields.append(line.Field("name", name_f))
        sequence_f = fv.validate(fields[1], cls.REQUIRED_FIELDS["sequence"])
        sfields.append(line.Field("sequence", sequence_f))

        for field in fields[2:]:
            sfields.append(line.OptField.from_string(field))

        for field in sfields:
            segment.add_field(field)
        return segment


def is_segmentv2(line_repr: str | line.Line) -> bool:
    """Check whether a given gfa line string probably belongs to a
    Segment of the second GFA version.

    :param line_repr: A string or a Line that is supposed to
        represent an S line.
    """
    try:
        if isinstance(line_repr, str):
            fields = re.split("\t", line_repr)
            # GFA2: S <name> <length> <sequence>
            if len(fields) >= 4 and fields[0] == "S":
                # Check if third field looks like a length (integer)
                if re.fullmatch(fv.DATASTRING_VALIDATION_REGEXP[fv.TYPE_i], fields[2]):
                    return True
        else:
            return line_repr.type == "S" and line_repr.fields.get("length") is not None
    except Exception:
        pass
    return False


class SegmentV2(line.Line):
    """A GFA2 Segment line."""

    def __init__(self):
        super().__init__("S")

    REQUIRED_FIELDS: Dict[str, str] = {
        "name": fv.GFA1_NAME,
        "length": fv.TYPE_i,
        "sequence": fv.GFA1_SEQUENCE,
    }

    PREDEFINED_OPTFIELDS: Dict[str, str] = {
        "LN": fv.TYPE_i,
        "RC": fv.TYPE_i,
        "FC": fv.TYPE_i,
        "KC": fv.TYPE_i,
        "SH": fv.HEX_BYTE_ARRAY,
        "UR": fv.TYPE_Z,
    }

    @classmethod
    def from_string(cls, string: str) -> "SegmentV2":
        """Extract the segment fields from the string.

        The string can contain the S character at the begin
        or can only contain the fields of the segment directly.
        GFA2 format: S <name> <length> <sequence> [optional fields]
        """
        if len(string.split()) == 0:
            raise line.InvalidLineError("Cannot parse the empty string.")
        fields = re.split("\t", string)
        sfields: list[line.Field | line.OptField] = []
        if fields[0] == "S":
            fields = fields[1:]

        if len(fields) < len(cls.REQUIRED_FIELDS):
            raise line.InvalidLineError("The minimum number of fields for SegmentV2 line is not reached.")

        segment = SegmentV2()
        name_f = fv.validate(fields[0], cls.REQUIRED_FIELDS["name"])
        sfields.append(line.Field("name", name_f))

        length_f = fv.validate(fields[1], cls.REQUIRED_FIELDS["length"])
        sfields.append(line.Field("length", length_f))

        sequence_f = fv.validate(fields[2], cls.REQUIRED_FIELDS["sequence"])
        sfields.append(line.Field("sequence", sequence_f))

        for field in fields[3:]:
            sfields.append(line.OptField.from_string(field))

        for field in sfields:
            segment.add_field(field)
        return segment


if __name__ == "__main__":  # pragma: no cover
    pass
