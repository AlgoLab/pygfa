from __future__ import annotations

import re
from typing import TYPE_CHECKING, Dict

if TYPE_CHECKING:
    pass

from pygfa.graph_element.parser import field_validator as fv
from pygfa.graph_element.parser import line
from pygfa.utils.string_utils import sanitize_string


class Path(line.Line):
    def __init__(self):
        super().__init__("P")

    REQUIRED_FIELDS: Dict[str, str] = {
        "path_name": fv.GFA1_NAME,
        "seqs_names": fv.GFA1_NAMES,
        "overlaps": fv.GFA1_CIGAR,
    }

    PREDEFINED_OPTFIELDS: Dict[str, str] = {}

    @classmethod
    def from_string(cls, string: str) -> Path:
        """Extract the path fields from the string.

        The string can contains the P character at the begin or can
        just contains the fields of the path directly.
        """
        if len(string.split()) == 0:
            raise line.InvalidLineError("Cannot parse the empty string.")
        fields = re.split("\t", string)
        pfields: list[line.Field | line.OptField] = []
        if fields[0] == "P":
            fields = fields[1:]

        if len(fields) < len(cls.REQUIRED_FIELDS):
            raise line.InvalidLineError("The minimum number of field for " + "Path line is not reached.")
        path = Path()
        path_name_raw = fields[0]
        path_name_sanitized, _ = sanitize_string(path_name_raw)
        path_name = fv.validate(path_name_sanitized, cls.REQUIRED_FIELDS["path_name"])

        sequences_names_raw = fields[1].split(",")
        sequences_names_sanitized = []
        for label in sequences_names_raw:
            label_sanitized, _ = sanitize_string(label)
            sequences_names_sanitized.append(fv.validate(label_sanitized, fv.GFA1_NAME))

        overlaps_raw = fields[2]
        overlaps_sanitized, _ = sanitize_string(overlaps_raw)
        overlaps = fv.validate(overlaps_sanitized, cls.REQUIRED_FIELDS["overlaps"])

        pfields.append(line.Field("path_name", path_name))
        pfields.append(line.Field("seqs_names", sequences_names_sanitized))
        pfields.append(line.Field("overlaps", overlaps))

        for field in fields[3:]:
            pfields.append(line.OptField.from_string(field))

        for field in pfields:
            path.add_field(field)

        return path


if __name__ == "__main__":  # pragma: no cover
    pass
