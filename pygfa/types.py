"""Type definitions for pygfa.

This module provides type definitions and protocols used throughout pygfa.
Uses Python 3.14+ type annotation features.
"""

from __future__ import annotations

from typing import Any, Optional, Protocol, TypeVar, Union

# Type variables
T = TypeVar("T")

# Basic type aliases
NodeId = str
EdgeId = Optional[str]
Sequence = str
Orientation = str  # "+" or "-"
CigarString = str
Position = Union[int, None]
NodePositions = tuple[Position, Position]


# Graph element protocols
class GraphElement(Protocol):
    """Protocol for graph elements (nodes, edges, paths, walks)."""

    @property
    def id(self) -> str:
        """Return element identifier."""
        ...


class NodeLike(Protocol):
    """Protocol for node-like objects."""

    @property
    def node_id(self) -> str:
        """Return node identifier."""
        ...

    @property
    def sequence(self) -> str:
        """Return DNA sequence."""
        ...

    @property
    def sequence_length(self) -> Optional[int]:
        """Return sequence length."""
        ...


class EdgeLike(Protocol):
    """Protocol for edge-like objects."""

    @property
    def edge_id(self) -> Optional[str]:
        """Return edge identifier."""
        ...

    @property
    def from_node(self) -> str:
        """Return source node ID."""
        ...

    @property
    def to_node(self) -> str:
        """Return target node ID."""
        ...

    @property
    def from_orientation(self) -> str:
        """Return source orientation."""
        ...

    @property
    def to_orientation(self) -> str:
        """Return target orientation."""
        ...


# Compression-related types
CompressionCode = int  # 2-byte compression code
EncodingType = Union[int, str]  # Integer or string encoding

# Optional fields type
OptFields = dict[str, Any]

__all__ = [
    "NodeId",
    "EdgeId",
    "Sequence",
    "Orientation",
    "CigarString",
    "Position",
    "NodePositions",
    "GraphElement",
    "NodeLike",
    "EdgeLike",
    "CompressionCode",
    "EncodingType",
    "OptFields",
    "T",
]
