"""Path graph element for pygfa.

Modern dataclass implementation with standardized naming.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List

from pygfa.exceptions import InvalidPathError

from pygfa.utils.string_utils import sanitize_string


@dataclass(frozen=True, slots=True)
class Path:
    """Represents a GFA path.

    A path is an ordered list of oriented segments with optional overlaps.

    Attributes:
        path_id: Path identifier
        segment_ids: List of segment IDs with orientations (e.g., ["s1+", "s2-"])
        overlaps: List of CIGAR overlap strings
        opt_fields: Optional fields as dictionary
    """

    path_id: str
    segment_ids: List[str]
    overlaps: List[str]
    opt_fields: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate path data after initialization."""
        if not self.path_id:
            raise InvalidPathError("Path ID cannot be empty")
        if not self.segment_ids:
            raise InvalidPathError("Path must have at least one segment")
        if len(self.overlaps) != len(self.segment_ids) - 1:
            # Allow empty overlaps or one less than segments
            if len(self.overlaps) > 0 and len(self.overlaps) != len(self.segment_ids) - 1:
                raise InvalidPathError(
                    f"Path with {len(self.segment_ids)} segments should have "
                    f"{len(self.segment_ids) - 1} overlaps, got {len(self.overlaps)}"
                )

    @property
    def id(self) -> str:
        """Return path ID (alias for path_id)."""
        return self.path_id

    @property
    def name(self) -> str:
        """Return path name (alias for path_id)."""
        return self.path_id

    @classmethod
    def from_line(cls, line: Any) -> Path:
        """Create Path from GFA line object.

        Args:
            line: GFA path line object

        Returns:
            New Path instance
        """

        if not hasattr(line, "fields"):
            raise InvalidPathError("Line object must have 'fields' attribute")

        fields = line.fields
        path_id_raw = fields.get("path_name", fields.get("pid", ""))
        if hasattr(path_id_raw, "value"):
            path_id_raw = path_id_raw.value

        path_id, _ = sanitize_string(path_id_raw)

        # Get segment names/orientations
        segment_ids = []
        if "segment_names" in fields:
            seg_names = fields["segment_names"]
            if hasattr(seg_names, "value"):
                segment_ids_raw = seg_names.value
            else:
                segment_ids_raw = seg_names
            segment_ids = []
            for seg_raw in segment_ids_raw:
                seg_sanitized, _ = sanitize_string(seg_raw)
                segment_ids.append(seg_sanitized)

        # Get overlaps
        overlaps = []
        if "overlaps" in fields:
            ov = fields["overlaps"]
            if hasattr(ov, "value"):
                overlaps_raw = ov.value
            else:
                overlaps_raw = ov
            overlaps = []
            for overlap_raw in overlaps_raw:
                overlap_sanitized, _ = sanitize_string(overlap_raw)
                overlaps.append(overlap_sanitized)

        # Extract optional fields
        opt_fields = {}
        for key, value in fields.items():
            if key not in ["path_name", "pid", "segment_names", "overlaps"]:
                opt_fields[key] = value

        return cls(path_id=path_id, segment_ids=segment_ids, overlaps=overlaps, opt_fields=opt_fields)

    def __len__(self) -> int:
        """Return number of segments in path."""
        return len(self.segment_ids)

    def __iter__(self):
        """Iterate over segment IDs."""
        return iter(self.segment_ids)

    def __str__(self) -> str:
        """String representation of Path."""
        return f"Path({self.path_id}: {' -> '.join(self.segment_ids)})"

    def __repr__(self) -> str:
        """Representation of Path."""
        return self.__str__()


__all__ = ["Path", "InvalidPathError"]
