"""Node (segment) graph element for pygfa.

Modern dataclass implementation with standardized naming.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Optional

from pygfa.exceptions import InvalidNodeError
from pygfa.graph_element.parser import field_validator as fv
from pygfa.graph_element.parser import line, segment

from pygfa.utils.string_utils import sanitize_string


def is_node(obj: Any) -> bool:
    """Check whether the given object is a Node object.

    :param obj: Any Python object.
    :returns: True if obj can be treated as a Node object.
    """
    try:
        return (
            obj.node_id is not None
            and obj.sequence is not None
            and hasattr(obj, "sequence_length")
            and hasattr(obj, "opt_fields")
        )
    except Exception:
        return False


@dataclass(frozen=True, slots=True)
class Node:
    """Represents a GFA segment (node).

    GFA graphs will operate on Nodes, by adding them directly to their
    structures.

    Attributes:
        node_id: Unique identifier for the node
        sequence: DNA sequence or "*" for unknown
        sequence_length: Length of the sequence (None if unknown)
        opt_fields: Optional fields as dictionary
    """

    node_id: str
    sequence: str
    sequence_length: Optional[int] = None
    opt_fields: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate node data after initialization."""
        # Use object.__setattr__ since dataclass is frozen
        if not isinstance(self.node_id, str) or self.node_id == "*":
            raise InvalidNodeError(
                f"A Node has always a defined id of type string, given {self.node_id} of type {type(self.node_id)}"
            )

        # Validate sequence - allow '*' for unknown sequences
        if not (
            isinstance(self.sequence, str) and (self.sequence == "*" or fv.is_valid(self.sequence, fv.GFA1_SEQUENCE))
        ):
            raise InvalidNodeError(
                "A sequence must be of type string and must be either '*' for unknown or a "
                f"valid GFA1 sequence, given '{self.sequence}' of type {type(self.sequence)}"
            )

        # Validate length
        if not (
            (isinstance(self.sequence_length, int) and int(self.sequence_length) >= 0) or self.sequence_length is None
        ):
            raise InvalidNodeError(
                f"Sequence length must be a number >= 0, "
                f"given {self.sequence_length} of type {type(self.sequence_length)}"
            )

    @property
    def nid(self) -> str:
        """Return node ID (deprecated alias, use node_id)."""
        return self.node_id

    @property
    def id(self) -> str:
        """Return node ID (alias for node_id)."""
        return self.node_id

    @property
    def seq(self) -> str:
        """Return sequence (alias for sequence)."""
        return self.sequence

    @property
    def slen(self) -> Optional[int]:
        """Return sequence length (deprecated alias, use sequence_length)."""
        return self.sequence_length

    @classmethod
    def from_line(cls, segment_line: line.Line) -> Node:
        """Given a Segment Line construct a Node from it.

        If segment_line is a GFA1 Segment line then the sequence length
        taken into account will be the value of the optional
        field `LN` if specified in the line fields.

        :param segment_line: A valid Segment Line.
        :raises InvalidNodeError: If the given line cannot be a Node.
        """
        try:
            fields = copy.deepcopy(segment_line.fields)
            if segment.is_segmentv1(segment_line):
                fields.pop("name")
                fields.pop("sequence")

                length = None
                if segment_line.fields["sequence"].value != "*":
                    length = len(segment_line.fields["sequence"].value)
                if "LN" in segment_line.fields:
                    length = segment_line.fields["LN"].value
                    fields.pop("LN")

                node_id, _ = sanitize_string(segment_line.fields["name"].value)
                sequence, _ = sanitize_string(segment_line.fields["sequence"].value)

                return cls(
                    node_id=node_id,
                    sequence=sequence,
                    sequence_length=length,
                    opt_fields=fields,
                )
            else:
                fields.pop("sid")
                fields.pop("sequence")
                fields.pop("slen")

                node_id, _ = sanitize_string(segment_line.fields["sid"].value)
                sequence, _ = sanitize_string(segment_line.fields["sequence"].value)

                return cls(
                    node_id=node_id,
                    sequence=sequence,
                    sequence_length=segment_line.fields["slen"].value,
                    opt_fields=fields,
                )
        except (KeyError, AttributeError) as err:
            raise InvalidNodeError("The given line cannot be a Node.") from err

    def __eq__(self, other: Any) -> bool:
        """Check equality with another Node."""
        if not isinstance(other, Node):
            return False
        if (
            self.node_id != other.node_id
            or self.sequence != other.sequence
            or self.sequence_length != other.sequence_length
        ):
            return False

        for key, item in self.opt_fields.items():
            if key not in other.opt_fields or self.opt_fields[key] != other.opt_fields[key]:
                return False

        return True

    def __str__(self) -> str:  # pragma: no cover
        """String representation of Node."""
        fields = ("node_id", "sequence", "sequence_length", "opt_fields")
        opt_fields_str = []
        if len(self.opt_fields) > 0:
            opt_fields_str = str.join(",\t", [str(field) for key, field in self.opt_fields.items()])
        values = (
            str(self.node_id),
            str(self.sequence),
            str(self.sequence_length),
            "{" + str(opt_fields_str) + "}",
        )
        assoc = [str.join(" : ", pair) for pair in zip(fields, values, strict=False)]
        return str.join(",\t", assoc)

    def is_dna(self) -> bool:
        """Check if sequence is valid DNA."""
        if self.sequence == "*":
            return False
        valid_chars = set("ACGTNacgtn")
        return all(c in valid_chars for c in self.sequence)


__all__ = ["Node", "is_node", "InvalidNodeError"]
