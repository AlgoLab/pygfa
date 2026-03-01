"""I/O module for pygfa.

Provides unified load/save functions for GFA and BGFA formats.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Union

from pygfa.gfa import GFA
from pygfa.encoding.enums import IntegerEncoding, StringEncoding

logger = logging.getLogger(__name__)


def load(path: Union[str, Path], format: Optional[str] = None) -> GFA:
    """Load a GFA file (auto-detects format from extension).

    Args:
        path: Path to GFA file (.gfa or .bgfa)
        format: Optional format hint ('gfa' or 'bgfa')

    Returns:
        GFA graph object

    Raises:
        FileNotFoundError: If file doesn't exist
        FileFormatError: If format cannot be determined or file is invalid
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    # Determine format from extension if not specified
    if format is None:
        if path.suffix == ".bgfa":
            format = "bgfa"
        elif path.suffix in (".gfa", ".gfal"):
            format = "gfa"
        else:
            # Try to detect from content
            with open(path, "rb") as f:
                header = f.read(4)
                if header == b"BGFA":
                    format = "bgfa"
                else:
                    format = "gfa"

    logger.info(f"Loading {format.upper()} file: {path}")

    if format == "bgfa":
        return GFA.from_bgfa(str(path))
    else:
        return GFA.from_gfa(str(path))


def save(
    graph: GFA,
    path: Union[str, Path],
    format: Optional[str] = None,
    gfa_version: int = 2,
    block_size: int = 1024,
    integer_encoding: IntegerEncoding = IntegerEncoding.VARINT,
    string_encoding: StringEncoding = StringEncoding.ZSTD,
) -> None:
    """Save a GFA graph to file (auto-detects format from extension).

    Args:
        graph: GFA graph to save
        path: Output file path
        format: Optional format hint ('gfa' or 'bgfa')
        gfa_version: GFA specification version (1 or 2) for text format
        block_size: Block size for binary format
        integer_encoding: Integer encoding for binary format
        string_encoding: String encoding for binary format
    """
    path = Path(path)

    # Determine format from extension if not specified
    if format is None:
        if path.suffix == ".bgfa":
            format = "bgfa"
        else:
            format = "gfa"

    logger.info(f"Saving {format.upper()} file: {path}")

    if format == "bgfa":
        compression_code = (integer_encoding.value << 8) | string_encoding.value
        graph.to_bgfa(str(path), block_size=block_size, compression_code=compression_code)
    else:
        graph.dump(gfa_version, str(path))


def load_text(path: Union[str, Path]) -> GFA:
    """Load a text GFA file.

    Args:
        path: Path to .gfa file

    Returns:
        GFA graph object
    """
    return load(path, format="gfa")


def load_binary(path: Union[str, Path]) -> GFA:
    """Load a binary BGFA file.

    Args:
        path: Path to .bgfa file

    Returns:
        GFA graph object
    """
    return load(path, format="bgfa")


def save_text(graph: GFA, path: Union[str, Path], version: int = 2) -> None:
    """Save as text GFA.

    Args:
        graph: GFA graph to save
        path: Output file path
        version: GFA specification version (1 or 2)
    """
    save(graph, path, format="gfa", gfa_version=version)


def save_binary(
    graph: GFA,
    path: Union[str, Path],
    block_size: int = 1024,
    integer_encoding: IntegerEncoding = IntegerEncoding.VARINT,
    string_encoding: StringEncoding = StringEncoding.ZSTD,
) -> None:
    """Save as binary BGFA.

    Args:
        graph: GFA graph to save
        path: Output file path
        block_size: Block size for binary format
        integer_encoding: Integer encoding strategy
        string_encoding: String encoding strategy
    """
    save(
        graph,
        path,
        format="bgfa",
        block_size=block_size,
        integer_encoding=integer_encoding,
        string_encoding=string_encoding,
    )


__all__ = [
    "load",
    "save",
    "load_text",
    "load_binary",
    "save_text",
    "save_binary",
]
