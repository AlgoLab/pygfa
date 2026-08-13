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


def decompress_string_dictionary(
    data: bytes, lengths: list[int], int_decoder: Callable | None = None
) -> list[bytes]:
    """Decompress dictionary-encoded strings.

    When *int_decoder* is provided, *data* is parsed as the list-dictionary
    payload emitted by ``compress_string_list_dictionary``:
    ``[dict_size:uint32][blob_len:uint32][dict_offsets][dict_blob][indices]``.
    Without it, *data* is treated as raw identity bytes (single-string mode).

    :param data: Compressed data
    :param lengths: List of original string lengths
    :param int_decoder: Integer list decoder (required for dictionary payloads)
    :return: List of decompressed byte sequences
    """
    if not data or not lengths:
        return []

    if int_decoder is None:
        # Single-string identity mode: extract strings by length.
        result = []
        offset = 0
        for length in lengths:
            if offset + length > len(data):
                raise ValueError(f"Data too short: need {offset + length} bytes, have {len(data)}")
            result.append(data[offset : offset + length])
            offset += length
        return result

    if len(data) < 8:
        raise ValueError("Malformed dictionary payload: too short for header")
    dict_size = struct.unpack_from("<I", data, 0)[0]
    blob_len = struct.unpack_from("<I", data, 4)[0]
    if blob_len > len(data) - 8:
        raise ValueError(
            f"Malformed dictionary payload: blob length {blob_len} exceeds available bytes {len(data) - 8}"
        )

    pos = 8
    offsets, consumed = int_decoder(data[pos:], dict_size)
    pos += consumed
    blob = data[pos : pos + blob_len]
    pos += blob_len
    indices, consumed2 = int_decoder(data[pos:], len(lengths))
    pos += consumed2

    result = []
    for idx in indices:
        if idx >= dict_size:
            raise ValueError(f"Malformed dictionary payload: index {idx} out of range (dict_size={dict_size})")
        start = offsets[idx]
        end = offsets[idx + 1] if idx + 1 < dict_size else blob_len
        result.append(blob[start:end])
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
    return compress_string_list_dictionary(string_list, compress_integer_list, max_dict_size)


def _decompress_string_dictionary_wrapper(payload: bytes, record_num: int, int_decoder: Callable) -> list[bytes]:
    lengths, consumed = int_decoder(payload, record_num)
    remaining = payload[consumed:]
    return decompress_string_dictionary(remaining, lengths, int_decoder)
