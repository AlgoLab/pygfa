"""
Edge module for GFA graph elements.

Modern dataclass implementation with standardized naming.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Optional, Tuple

from pygfa.exceptions import InvalidEdgeError
from pygfa.graph_element.parser import containment, line, link


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


@dataclass(frozen=True, slots=True)
class Edge:
    """An edge in a GFA graph.

    Represents connections between nodes (segments) and can be derived from
    Link (L) or Containment (C) lines in GFA1 format.

    Attributes:
        edge_id: Edge identifier, can be None (virtual edge)
        from_node: Source node identifier
        from_orientation: Source orientation (+ or -)
        to_node: Target node identifier
        to_orientation: Target orientation (+ or -)
        from_positions: Tuple of (start, end) positions on source
        to_positions: Tuple of (start, end) positions on target
        alignment: Alignment string (CIGAR, trace, etc.)
        distance: Distance for gap edges
        variance: Variance for gap edges
        opt_fields: Optional fields dictionary
    """

    edge_id: Optional[str]
    from_node: str
    from_orientation: str
    to_node: str
    to_orientation: str
    from_positions: Tuple[Optional[int], Optional[int]]
    to_positions: Tuple[Optional[int], Optional[int]]
    alignment: str
    distance: Optional[int] = None
    variance: Optional[str] = None
    opt_fields: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate edge data after initialization."""
        if not self.from_node:
            raise InvalidEdgeError("from_node cannot be empty")
        if not self.to_node:
            raise InvalidEdgeError("to_node cannot be empty")
        if self.from_orientation not in ("+", "-"):
            raise InvalidEdgeError(f"from_orientation must be '+' or '-', got {self.from_orientation}")
        if self.to_orientation not in ("+", "-"):
            raise InvalidEdgeError(f"to_orientation must be '+' or '-', got {self.to_orientation}")

    @property
    def eid(self) -> Optional[str]:
        """Return edge ID (deprecated alias, use edge_id)."""
        return self.edge_id

    @property
    def id(self) -> Optional[str]:
        """Return edge ID (alias for edge_id)."""
        return self.edge_id

    @property
    def from_orn(self) -> str:
        """Return from orientation (deprecated alias, use from_orientation)."""
        return self.from_orientation

    @property
    def to_orn(self) -> str:
        """Return to orientation (deprecated alias, use to_orientation)."""
        return self.to_orientation

    @classmethod
    def from_line(cls, edge_line: line.Line) -> Optional[Edge]:
        """Create an Edge from a Link or Containment line.

        :param edge_line: A line object to convert to an Edge
        :return: Edge object, or None if edge_line cannot be converted
        """
        # Handle Link lines (type 'L')
        if isinstance(edge_line, link.Link):
            fields = edge_line.fields

            # Check for ID in optional fields - use "*" as default per GFA spec
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
                edge_id=eid,
                from_node=from_node,
                from_orientation=from_orn,
                to_node=to_node,
                to_orientation=to_orn,
                from_positions=from_positions,
                to_positions=to_positions,
                alignment=alignment,
                distance=distance,
                variance=variance,
                opt_fields=opt_fields,
            )

        # Handle Containment lines (type 'C')
        if isinstance(edge_line, containment.Containment):
            fields = edge_line.fields

            # Check for ID in optional fields - use "*" as default per GFA spec
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
                edge_id=eid,
                from_node=from_node,
                from_orientation=from_orn,
                to_node=to_node,
                to_orientation=to_orn,
                from_positions=from_positions,
                to_positions=to_positions,
                alignment=alignment,
                distance=distance,
                variance=variance,
                opt_fields=opt_fields,
            )

        # Not a Link or Containment line, cannot convert
        return None

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Edge):
            return False
        return (
            self.edge_id == other.edge_id
            and self.from_node == other.from_node
            and self.from_orientation == other.from_orientation
            and self.to_node == other.to_node
            and self.to_orientation == other.to_orientation
            and self.from_positions == other.from_positions
            and self.to_positions == other.to_positions
            and self.alignment == other.alignment
            and self.distance == other.distance
            and self.variance == other.variance
            and self.opt_fields == other.opt_fields
        )

    def __str__(self) -> str:
        return f"Edge({self.edge_id}: {self.from_node}{self.from_orientation} -> {self.to_node}{self.to_orientation})"

    def __repr__(self) -> str:
        return self.__str__()


__all__ = ["Edge", "is_edge", "InvalidEdgeError"]
