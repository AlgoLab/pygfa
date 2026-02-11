"""Custom exceptions for pygfa.

This module provides standardized exceptions for all GFA-related errors.
"""

from __future__ import annotations


class GFAError(Exception):
    """Base exception for GFA-related errors."""

    pass


class InvalidNodeError(GFAError):
    """Raised when a node is invalid or cannot be created."""

    pass


class InvalidEdgeError(GFAError):
    """Raised when an edge is invalid or cannot be created."""

    pass


class InvalidPathError(GFAError):
    """Raised when a path is invalid or cannot be created."""

    pass


class InvalidWalkError(GFAError):
    """Raised when a walk is invalid or cannot be created."""

    pass


class InvalidSubgraphError(GFAError):
    """Raised when a subgraph is invalid or cannot be created."""

    pass


class InvalidElementError(GFAError):
    """Raised when a graph element is invalid or not found."""

    pass


class InvalidSearchParameters(GFAError):
    """Raised when search parameters are invalid."""

    pass


class InvalidEncodingError(GFAError):
    """Raised when an encoding is invalid or unsupported."""

    pass


class InvalidCompressionError(GFAError):
    """Raised when compression or decompression fails."""

    pass


class FileFormatError(GFAError):
    """Raised when a file format is invalid or unsupported."""

    pass


class DictionaryTrainingError(GFAError):
    """Raised when dictionary training fails."""

    pass


__all__ = [
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
