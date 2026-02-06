import re

from pygfa.graph_element.parser import line, field_validator as fv


class Walk(line.Line):
    def __init__(self):
        super().__init__("W")

    REQUIRED_FIELDS = {
        "SampleId": fv.GFA1_NAME,
        "HapIndex": fv.GFA1_NAME,
        "SeqId": fv.GFA1_NAME,
        "SeqStart": fv.GFA2_INT,
        "SeqEnd": fv.GFA2_INT,
        "Walk": fv.GFA1_NAMES,
    }

    PREDEFINED_OPTFIELDS = {
        "SC": fv.TYPE_i,
    }

    @classmethod
    def from_string(cls, string: str) -> "Walk":
        """Extract the walk fields from the string.

        The string can contains the W character at the begin or can
        just contains the fields of the walk directly.

        :param string: The input string containing walk data.
        :return: A Walk instance parsed from the string.
        :raises line.InvalidLineError: If the string is empty or has insufficient fields.
        """
        if len(string.split()) == 0:
            raise line.InvalidLineError("Cannot parse the empty string.")
        fields = re.split("\t", string)
        pfields = []
        if fields[0] == "W":
            fields = fields[1:]

        if len(fields) < len(cls.REQUIRED_FIELDS):
            raise line.InvalidLineError(
                "The minimum number of field for " + "Walk line is not reached."
            )
        walk = Walk()
        walk_name = fv.validate(fields[0], cls.REQUIRED_FIELDS["walk_name"])
        sequences_names = [
            fv.validate(label, cls.REQUIRED_FIELDS["seqs_names"]) for label in fields[1].split(",")
        ]

        overlaps = fv.validate(fields[2], cls.REQUIRED_FIELDS["overlaps"])

        pfields.append(line.Field("walk_name", walk_name))
        pfields.append(line.Field("seqs_names", sequences_names))
        pfields.append(line.Field("overlaps", overlaps))

        for field in fields[3:]:
            pfields.append(line.OptField.from_string(field))

        for field in pfields:
            walk.add_field(field)

        return walk


if __name__ == "__main__":  # pragma: no cover
    pass
