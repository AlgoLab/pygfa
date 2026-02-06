"""
Edge module for GFA graph elements.
"""

import copy
from typing import Any

from pygfa.graph_element.parser import containment, fragment, gap, line, link
from pygfa.graph_element.parser.edge import Edge as EdgeLine


class InvalidEdgeError(Exception):
    pass


def is_edge(obj: Any) -> bool:
    """Return True if the given object can be treated as an Edge.

    Supports duck typing - checks for required attributes with non-None values.
    """
    try:
        return (
            obj.from_node is not None
            and obj.from_orn is not None
            and obj.to_node is not None
            and obj.to_orn is not None
            and obj.alignment is not None
            and hasattr(obj, "opt_fields")
        )
    except Exception:
        return False


class Edge:
    """Represents an edge in a GFA graph.

    An edge connects two nodes (segments) with orientations and may have
    an overlap specified as a CIGAR string.
    """

    def __init__(
        self,
        eid: str | None,
        from_node: str | None,
        from_orn: str | None,
        to_node: str | None,
        to_orn: str | None,
        from_positions: tuple[int | None, int | None],
        to_positions: tuple[int | None, int | None],
        alignment: str | None,
        distance: int | None,
        variance: str | None,
        opt_fields: dict[str, line.Field] | None = None,
        is_dovetail: bool = False,
    ) -> None:
        """Initialize an Edge object.

        :param eid: Edge identifier (can be None for virtual edges)
        :param from_node: Source node identifier
        :param from_orn: Source orientation ('+' or '-')
        :param to_node: Destination node identifier
        :param to_orn: Destination orientation ('+' or '-')
        :param from_positions: Tuple of (start, end) positions on source node
        :param to_positions: Tuple of (start, end) positions on destination node
        :param alignment: CIGAR string describing the overlap
        :param distance: Distance between nodes
        :param variance: Variance of the distance
        :param opt_fields: Dictionary of optional fields
        :param is_dovetail: Whether this is a dovetail overlap
        """
        if opt_fields is None:
            opt_fields = {}
        self.eid = eid
        self.from_node = from_node
        self.from_orn = from_orn
        self.to_node = to_node
        self.to_orn = to_orn
        self.from_positions = from_positions
        self.to_positions = to_positions
        self.alignment = alignment
        self.distance = distance
        self.variance = variance
        self._opt_fields = {}
        for key, field in opt_fields.items():
            if line.is_field(field):
                self._opt_fields[key] = copy.deepcopy(field)
        self.is_dovetail = is_dovetail

        # Add segment end attributes (used for dovetail operations)
        self.from_segment_end = None
        self.to_segment_end = None

        # Validate required fields
        if from_node is None:
            raise InvalidEdgeError("from_node cannot be None")
        if to_node is None:
            raise InvalidEdgeError("to_node cannot be None")
        # Only validate orientation for dovetail edges
        if is_dovetail:
            if from_orn not in ["+", "-"]:
                raise InvalidEdgeError(f"Invalid from_orn: {from_orn}")
            if to_orn not in ["+", "-"]:
                raise InvalidEdgeError(f"Invalid to_orn: {to_orn}")

        # Validate positions
        if not isinstance(from_positions, tuple) or len(from_positions) != 2:
            raise InvalidEdgeError(f"Invalid from_positions tuple: given: {from_positions!s}")
        if not isinstance(to_positions, tuple) or len(to_positions) != 2:
            raise InvalidEdgeError(f"Invalid to_positions tuple: given: {to_positions!s}")

    @property
    def opt_fields(self) -> dict[str, line.Field]:
        return self._opt_fields

    @classmethod
    def from_line(cls, edge_line: line.Line) -> Edge | None:
        """Create an Edge from an EdgeLine, Link, Containment, Fragment, or Gap line.

        :param edge_line: A line object to convert to an Edge
        :return: Edge object, or None if edge_line cannot be converted
        :raises line.InvalidLineError: If edge_line has type 'E' but is not a valid EdgeLine
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
                is_dovetail=True,
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
                is_dovetail=False,
            )

        # Handle Fragment lines (type 'F')
        if isinstance(edge_line, fragment.Fragment):
            fields = edge_line.fields
            eid = fields.get("eid", None)

            from_node = fields.get("sid").value
            from_orn = None
            to_node = fields.get("external").value[:-1]
            to_orn = fields.get("external").value[-1:]

            sbeg = fields.get("sbeg")
            send = fields.get("send")
            from_positions = (
                sbeg.value if sbeg is not None else None,
                send.value if send is not None else None,
            )

            fbeg = fields.get("fbeg")
            fend = fields.get("fend")
            to_positions = (
                fbeg.value if fbeg is not None else None,
                fend.value if fend is not None else None,
            )

            alignment = fields.get("alignment").value

            distance = None
            variance = None

            # Extract optional fields
            opt_fields = {}
            for key, value in fields.items():
                if key not in [
                    "eid",
                    "sid",
                    "external",
                    "sbeg",
                    "send",
                    "fbeg",
                    "fend",
                    "alignment",
                ]:
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
                is_dovetail=False,
            )

        # Handle Gap lines (type 'G')
        if isinstance(edge_line, gap.Gap):
            fields = edge_line.fields
            eid = fields.get("gid", None)
            if eid is not None:
                eid = eid.value
            else:
                eid = "*"

            sid1 = fields.get("sid1")
            from_node = sid1.value[:-1]
            from_orn = sid1.value[-1:]

            sid2 = fields.get("sid2")
            to_node = sid2.value[:-1]
            to_orn = sid2.value[-1:]

            dist = fields.get("distance")
            distance = dist.value if dist is not None else None

            var = fields.get("variance")
            variance = var.value if var is not None else "*"

            alignment = "*"
            from_positions = (None, None)
            to_positions = (None, None)

            # Extract optional fields (excluding standard fields)
            opt_fields = {}
            for key, value in fields.items():
                if key not in ["gid", "sid1", "sid2", "distance", "variance"]:
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
                is_dovetail=False,
            )

        # Handle Edge lines (type 'E')
        if not isinstance(edge_line, EdgeLine):
            if hasattr(edge_line, "type") and edge_line.type == "E":
                raise line.InvalidLineError("The given line cannot be converted to an Edge.")
            return None

        # Extract fields from the EdgeLine
        fields = edge_line.fields

        eid = fields.get("eid", None)
        if eid is not None:
            eid = eid.value

        # Extract from_node and from_orn from sid1 (e.g., "23-" -> "23", "-")
        sid1 = fields.get("sid1")
        if sid1 is not None:
            sid1_value = sid1.value
            from_node = sid1_value[:-1]
            from_orn = sid1_value[-1]
        else:
            from_node = None
            from_orn = None

        # Extract to_node and to_orn from sid2 (e.g., "16+" -> "16", "+")
        sid2 = fields.get("sid2")
        if sid2 is not None:
            sid2_value = sid2.value
            to_node = sid2_value[:-1]
            to_orn = sid2_value[-1]
        else:
            to_node = None
            to_orn = None

        # Extract positions
        beg1 = fields.get("beg1")
        end1 = fields.get("end1")
        from_positions = (
            beg1.value if beg1 is not None else None,
            end1.value if end1 is not None else None,
        )

        beg2 = fields.get("beg2")
        end2 = fields.get("end2")
        to_positions = (
            beg2.value if beg2 is not None else None,
            end2.value if end2 is not None else None,
        )

        alignment_field = fields.get("alignment")
        alignment = alignment_field.value if alignment_field is not None else None

        distance = fields.get("distance", None)
        if distance is not None:
            distance = distance.value

        variance = fields.get("variance", None)
        if variance is not None:
            variance = variance.value

        # Extract optional fields
        opt_fields = {}
        for key, value in fields.items():
            if key not in [
                "eid",
                "sid1",
                "sid2",
                "beg1",
                "end1",
                "beg2",
                "end2",
                "alignment",
                "distance",
                "variance",
                "is_dovetail",
            ]:
                opt_fields[key] = value

        is_dovetail = fields.get("is_dovetail", False)

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
            is_dovetail,
        )

    def __eq__(self, other: Any) -> bool:
        """Check if two edges are equal (ignoring IDs).

        Supports duck typing - compares with any object that has
        the required attributes.
        """
        try:
            return (
                self.from_node == other.from_node
                and self.from_orn == other.from_orn
                and self.to_node == other.to_node
                and self.to_orn == other.to_orn
                and self.alignment == other.alignment
                and self.distance == other.distance
                and self.variance == other.variance
                and self.is_dovetail == other.is_dovetail
                and self.opt_fields == other.opt_fields
            )
        except Exception:
            return False

    def __repr__(self) -> str:
        return f"Edge({self.from_node}{self.from_orn}->{self.to_node}{self.to_orn})"
