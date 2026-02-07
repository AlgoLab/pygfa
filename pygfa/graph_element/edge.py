"""
Edge module for GFA graph elements.
"""

import copy
from typing import Any

from pygfa.graph_element.parser import containment, line, link


class InvalidEdgeError(Exception):
    pass


def is_edge(obj: Any) -> bool:
    """Return True if the given object can be treated as an Edge.

    Supports duck typing - checks for required attributes with non-None values.
    """
    try:
        return (
            obj.from_node is not None
            and obj.to_node is not None
            and obj.alignment is not None
            and hasattr(obj, "opt_fields")
        )
    except Exception:
        return False


class Edge:
    """An edge in a GFA graph.

    Represents connections between nodes (segments) and can be derived from
    Link (L) or Containment (C) lines in GFA1 format.
    """

    def __init__(
        self,
        eid: str | None,
        from_node: str,
        from_orn: str,
        to_node: str,
        to_orn: str,
        from_positions: tuple[int | None, int | None],
        to_positions: tuple[int | None, int | None],
        alignment: str,
        distance: int | None,
        variance: str | None,
        opt_fields: dict[str, line.Field] | None = None,
    ) -> None:
        """Create an Edge.

        :param eid: Edge identifier, can be None (virtual edge)
        :param from_node: Source node identifier
        :param from_orn: Source orientation (+ or -)
        :param to_node: Target node identifier
        :param to_orn: Target orientation (+ or -)
        :param from_positions: Tuple of (start, end) positions on source
        :param to_positions: Tuple of (start, end) positions on target
        :param alignment: Alignment string (CIGAR, trace, etc.)
        :param distance: Distance for gap edges
        :param variance: Variance for gap edges
        :param opt_fields: Optional fields dictionary
        """
        if opt_fields is None:
            opt_fields = {}

        self._eid = eid
        self._from_node = from_node
        self._from_orn = from_orn
        self._to_node = to_node
        self._to_orn = to_orn
        self._from_positions = from_positions
        self._to_positions = to_positions
        self._alignment = alignment
        self._distance = distance
        self._variance = variance
        self._opt_fields = {}
        for key, field in opt_fields.items():
            if line.is_field(field):
                self._opt_fields[key] = copy.deepcopy(field)

    @classmethod
    def from_line(cls, edge_line: line.Line) -> Edge | None:
        """Create an Edge from a Link or Containment line.

        :param edge_line: A line object to convert to an Edge
        :return: Edge object, or None if edge_line cannot be converted
        """
        # Handle Link lines (type 'L')
        if isinstance(edge_line, link.Link):
            fields = edge_line.fields

            # Check for ID in optional fields
            eid = "*"
            if "ID" in fields:
                eid = fields["ID"].value

            from_node = fields.get("from").value
            from_orn = fields.get("from_orn").value
            to_node = fields.get("to").value
            to_orn = fields.get("to_orn").value

            overlap = fields.get("overlap")
            alignment = overlap.value if overlap is not None else "*"

            distance = None
            variance = None
            from_positions = (None, None)
            to_positions = (None, None)

            # Extract optional fields (excluding ID which we already handled)
            opt_fields = {}
            for key, value in fields.items():
                if key not in ["from", "from_orn", "to", "to_orn", "overlap", "ID"]:
                    opt_fields[key] = value

            return cls(
                eid,
                from_node,
                from_orn,
                to_node,
                to_orn,
                from_positions,
                to_positions,
                alignment,
                distance,
                variance,
                opt_fields,
            )

        # Handle Containment lines (type 'C')
        if isinstance(edge_line, containment.Containment):
            fields = edge_line.fields

            # Check for ID in optional fields
            eid = "*"
            if "ID" in fields:
                eid = fields["ID"].value

            from_node = fields.get("from").value
            from_orn = fields.get("from_orn").value
            to_node = fields.get("to").value
            to_orn = fields.get("to_orn").value

            pos = fields.get("pos")
            position = pos.value if pos is not None else None

            overlap = fields.get("overlap")
            alignment = overlap.value if overlap is not None else "*"

            distance = None
            variance = None
            from_positions = (None, None)
            to_positions = (None, None)

            # Extract optional fields (excluding standard fields and ID)
            opt_fields = {}
            for key, value in fields.items():
                if key not in ["from", "from_orn", "to", "to_orn", "pos", "overlap", "ID"]:
                    opt_fields[key] = value
            if position is not None:
                opt_fields["pos"] = line.Field("pos", position)

            return cls(
                eid,
                from_node,
                from_orn,
                to_node,
                to_orn,
                from_positions,
                to_positions,
                alignment,
                distance,
                variance,
                opt_fields,
            )

        # Not a Link or Containment line, cannot convert
        return None

    @property
    def eid(self) -> str | None:
        return self._eid

    @property
    def from_node(self) -> str:
        return self._from_node

    @property
    def from_orn(self) -> str:
        return self._from_orn

    @property
    def to_node(self) -> str:
        return self._to_node

    @property
    def to_orn(self) -> str:
        return self._to_orn

    @property
    def from_positions(self) -> tuple[int | None, int | None]:
        return self._from_positions

    @property
    def to_positions(self) -> tuple[int | None, int | None]:
        return self._to_positions

    @property
    def alignment(self) -> str:
        return self._alignment

    @property
    def distance(self) -> int | None:
        return self._distance

    @property
    def variance(self) -> str | None:
        return self._variance

    @property
    def opt_fields(self) -> dict[str, line.Field]:
        return self._opt_fields

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Edge):
            return False
        return (
            self._eid == other._eid
            and self._from_node == other._from_node
            and self._from_orn == other._from_orn
            and self._to_node == other._to_node
            and self._to_orn == other._to_orn
            and self._from_positions == other._from_positions
            and self._to_positions == other._to_positions
            and self._alignment == other._alignment
            and self._distance == other._distance
            and self._variance == other._variance
            and self._opt_fields == other._opt_fields
        )

    def __str__(self) -> str:
        return f"Edge({self._eid}: {self._from_node}{self._from_orn} -> {self._to_node}{self._to_orn})"

    def __repr__(self) -> str:
        return self.__str__()
