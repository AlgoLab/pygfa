from __future__ import annotations

import gzip
import lzma
from typing import Callable, Optional

try:
    import compression.zstd as z

    _ZSTD_AVAILABLE = True
except ImportError:
    _ZSTD_AVAILABLE = False
    z = None


def compress_string_zstd(string: str) -> bytes:
    if not _ZSTD_AVAILABLE:
        raise ImportError(
            "The 'compression' package is required for zstd compression. "
            "Install it with: pip install compression"
        )
    return z.compress(string.encode("ascii"), level=19)


def compress_string_gzip(string: str) -> bytes:
    return gzip.compress(string.encode("ascii"))


def compress_string_lzma(string: str) -> bytes:
    return lzma.compress(string.encode("ascii"))


def compress_string_none(string: str) -> bytes:
    return string.encode("ascii")


def compress_string_list(
    string_list: list[str],
    compress_integer_list: Optional[Callable[[list[int]], bytes]] = None,
    compression_method: str = "zstd",
    compression_level: int = 19,
) -> bytes:
    strings = [string.encode("ascii") for string in string_list]
    length_bytes = compress_integer_list([len(s) for s in strings])

    concatenated_strings = b"".join(strings)

    if compression_method == "zstd":
        if not _ZSTD_AVAILABLE:
            raise ImportError(
                "The 'compression' package is required for zstd compression. "
                "Install it with: pip install compression"
            )
        compressed_data = z.compress(concatenated_strings, level=compression_level)
    elif compression_method == "gzip":
        compressed_data = gzip.compress(concatenated_strings, compresslevel=compression_level)
    elif compression_method == "lzma":
        compressed_data = lzma.compress(concatenated_strings, preset=compression_level)
    elif compression_method == "none":
        compressed_data = concatenated_strings
    else:
        raise ValueError(f"Unsupported compression method: {compression_method}")

    return length_bytes + compressed_data
