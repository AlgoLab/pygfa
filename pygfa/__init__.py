"""pygfa - Graphical Fragment Assembly library.

A modern Python library for working with GFA (Graphical Fragment Assembly) files.
"""

from __future__ import annotations

# Core GFA class
from pygfa.gfa import GFA

# Core modules
from pygfa import bgfa, gfa
from pygfa.bgfa import to_bgfa  # noqa: F401
from pygfa.operations import nodes_connected_component, nodes_connected_components  # noqa: F401

# Type definitions
from pygfa.types import (
    NodeId,
    EdgeId,
    Sequence,
    Orientation,
    CigarString,
    Position,
    NodePositions,
)

# Exceptions
from pygfa.exceptions import (
    GFAError,
    InvalidNodeError,
    InvalidEdgeError,
    InvalidPathError,
    InvalidWalkError,
    InvalidSubgraphError,
    InvalidElementError,
    InvalidSearchParameters,
    InvalidEncodingError,
    InvalidCompressionError,
    FileFormatError,
    DictionaryTrainingError,
)

__version__ = "2.0.0"
__all__ = [
    # Core
    "GFA",
    "bgfa",
    "gfa",
    # Operations
    "nodes_connected_component",
    "nodes_connected_components",
    "to_bgfa",
    # Types
    "NodeId",
    "EdgeId",
    "Sequence",
    "Orientation",
    "CigarString",
    "Position",
    "NodePositions",
    # Exceptions
    "GFAError",
    "InvalidNodeError",
    "InvalidEdgeError",
    "InvalidPathError",
    "InvalidWalkError",
    "InvalidSubgraphError",
    "InvalidElementError",
    "InvalidSearchParameters",
    "InvalidEncodingError",
    "InvalidCompressionError",
    "FileFormatError",
    "DictionaryTrainingError",
]
