from __future__ import annotations

import gzip
import lzma
from typing import IO, Any

try:
    import compression.zstd as z

    _ZSTD_AVAILABLE = True
except ImportError:
    _ZSTD_AVAILABLE = False
    z = None  # type: ignore


def open_gfa_file(filepath: str, mode: str = "r") -> IO[Any]:
    """Open GFA file with support for gzip, zstd, and xz compression.

    Supports the following file formats:
    - Plain text GFA files (*.gfa)
    - Gzip-compressed files (*.gfa.gz)
    - Zstd-compressed files (*.gfa.zst, *.gfa.zstd)
    - XZ/LZMA-compressed files (*.gfa.xz)

    Args:
        filepath: Path to the file
        mode: File mode ('r' for text, 'rb' for binary)

    Returns:
        File handle

    Raises:
        ImportError: If zstd compression is requested but compression package is not installed
    """
    text_mode = "b" not in mode

    if filepath.endswith(".zst") or filepath.endswith(".zstd"):
        if not _ZSTD_AVAILABLE:
            raise ImportError(
                "The 'compression' package is required for zstd compression. "
                "Install it with: pip install compression"
            )
        assert z is not None
        return z.open(filepath, "rt" if text_mode else "rb")  # type: ignore

    elif filepath.endswith(".xz"):
        return lzma.open(filepath, "rt" if text_mode else "rb")

    elif filepath.endswith(".gz"):
        return gzip.open(filepath, "rt" if text_mode else "rb")  # type: ignore

    else:
        return open(filepath, mode)
