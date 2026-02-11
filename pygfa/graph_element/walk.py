"""Walk graph element for pygfa.

Modern dataclass implementation with standardized naming.
Walks are introduced in GFA 1.1 and represent haplotype paths.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional

from pygfa.exceptions import InvalidWalkError


@dataclass(frozen=True, slots=True)
class Walk:
    """Represents a GFA walk (haplotype path).

    Walks are similar to paths but include sample metadata and are
    designed for representing pangenome haplotypes.

    Attributes:
        walk_id: Walk identifier
        sample_id: Sample identifier (e.g., "HG001")
        haplotype_index: Haplotype index (0 or 1 for diploid)
        sequence_id: Sequence/chromosome identifier (e.g., "chr1")
        start: Start position on reference
        end: End position on reference
        segment_ids: List of segment IDs with orientations
        opt_fields: Optional fields as dictionary
    """

    walk_id: str
    sample_id: str
    haplotype_index: int
    sequence_id: str
    start: int
    end: int
    segment_ids: List[str]
    opt_fields: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate walk data after initialization."""
        if not self.walk_id:
            raise InvalidWalkError("Walk ID cannot be empty")
        if not self.sample_id:
            raise InvalidWalkError("Sample ID cannot be empty")
        if not self.sequence_id:
            raise InvalidWalkError("Sequence ID cannot be empty")
        if self.haplotype_index < 0:
            raise InvalidWalkError("Haplotype index must be non-negative")
        if self.start < 0:
            raise InvalidWalkError("Start position must be non-negative")
        if self.end < self.start:
            raise InvalidWalkError("End position must be >= start position")
        if not self.segment_ids:
            raise InvalidWalkError("Walk must have at least one segment")

    @property
    def id(self) -> str:
        """Return walk ID (alias for walk_id)."""
        return self.walk_id

    @property
    def length(self) -> int:
        """Return length of walk in base pairs."""
        return self.end - self.start

    @property
    def path_id(self) -> str:
        """Return walk identifier in path format."""
        return f"{self.sample_id}#{self.haplotype_index}#{self.sequence_id}:{self.start}-{self.end}"

    @classmethod
    def from_line(cls, line: Any) -> Walk:
        """Create Walk from GFA line object.

        Args:
            line: GFA walk line object

        Returns:
            New Walk instance
        """
        from pygfa.graph_element.parser import line as line_module

        if not hasattr(line, "fields"):
            raise InvalidWalkError("Line object must have 'fields' attribute")

        fields = line.fields

        # Extract required fields
        sample_id = fields.get("sample", fields.get("sample_id", ""))
        if hasattr(sample_id, "value"):
            sample_id = sample_id.value

        hap_idx = fields.get("hap_idx", 0)
        if hasattr(hap_idx, "value"):
            hap_idx = hap_idx.value

        seq_id = fields.get("seq_id", fields.get("sequence_id", ""))
        if hasattr(seq_id, "value"):
            seq_id = seq_id.value

        start = fields.get("start", 0)
        if hasattr(start, "value"):
            start = start.value

        end = fields.get("end", 0)
        if hasattr(end, "value"):
            end = end.value

        # Get segment names/orientations
        segment_ids = []
        if "segment_names" in fields:
            seg_names = fields["segment_names"]
            if hasattr(seg_names, "value"):
                segment_ids = seg_names.value
            else:
                segment_ids = seg_names

        # Generate walk ID if not present
        walk_id = f"{sample_id}#{hap_idx}#{seq_id}"

        # Extract optional fields
        opt_fields = {}
        for key, value in fields.items():
            if key not in ["sample", "sample_id", "hap_idx", "seq_id", "sequence_id", "start", "end", "segment_names"]:
                opt_fields[key] = value

        return cls(
            walk_id=walk_id,
            sample_id=sample_id,
            haplotype_index=hap_idx,
            sequence_id=seq_id,
            start=start,
            end=end,
            segment_ids=segment_ids,
            opt_fields=opt_fields,
        )

    def __len__(self) -> int:
        """Return number of segments in walk."""
        return len(self.segment_ids)

    def __iter__(self):
        """Iterate over segment IDs."""
        return iter(self.segment_ids)

    def __str__(self) -> str:
        """String representation of Walk."""
        return f"Walk({self.walk_id}: {' -> '.join(self.segment_ids)})"

    def __repr__(self) -> str:
        """Representation of Walk."""
        return self.__str__()


__all__ = ["Walk", "InvalidWalkError"]
