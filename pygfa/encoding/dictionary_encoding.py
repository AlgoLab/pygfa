"""Dictionary-based encoding for repetitive identifiers.

Highly effective for:
- Sample IDs that repeat across thousands of walks
- Segment names with common prefixes
- Path names with structural patterns

Replaces repeated strings with varint references to a dictionary, achieving
60-90% compression on highly repetitive data.
"""

from __future__ import annotations

import struct
from collections.abc import Callable

from pygfa.encoding.string_encoding import compress_string_list_dictionary


def compress_string_dictionary(string: str) -> bytes:
    """Compress a single string using dictionary encoding.

    Note: Dictionary encoding is most effective on lists of strings.
    For single strings, this returns the raw string (identity encoding).

    :param string: Input string
    :return: Compressed bytes
    """
    return string.encode("ascii")


def decompress_string_dictionary(data: bytes, lengths: list[int]) -> list[bytes]:
    """Decompress dictionary-encoded strings.

    For compatibility with BGFA, this function works in identity mode:
    it simply extracts strings using the provided lengths.

    Dictionary encoding is most effective when used via compress_string_list_dictionary,
    but BGFA uses single-string encoders, so we fall back to identity decoding.

    :param data: Compressed data
    :param lengths: List of original string lengths
    :return: List of decompressed byte sequences
    """
    if not data or not lengths:
        return []

    # Simple identity decoding: extract strings by length
    result = []
    offset = 0
    for length in lengths:
        if offset + length > len(data):
            raise ValueError(f"Data too short: need {offset + length} bytes, have {len(data)}")
        result.append(data[offset : offset + length])
        offset += length
    return result


def compress_string_list_dictionary_wrapper(
    string_list: list[str],
    compress_integer_list: Callable[[list[int]], bytes] | None = None,
    max_dict_size: int = 65536,
) -> bytes:
    """Compress a list of strings using dictionary encoding.

    This wraps the existing compress_string_list_dictionary function.

    :param string_list: List of strings
    :param compress_integer_list: Integer compression function (passed to dictionary encoder)
    :param max_dict_size: Maximum dictionary size
    :return: Compressed bytes
    """
    return compress_string_list_dictionary(
        string_list, compress_integer_list, max_dict_size
    )
