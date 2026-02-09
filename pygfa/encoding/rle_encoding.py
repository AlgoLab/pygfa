"""Run-Length Encoding (RLE) for sequences with repetitive characters.

RLE is effective for:
- DNA sequences with homopolymers (AAAAAAA, GGGGGG, TTTTTT)
- CIGAR strings with repeated operations (100M, 50D)
- Any string data with character runs

This implementation uses a hybrid mode that switches between raw and RLE encoding
within a string to avoid expansion on non-repetitive data.
"""

from __future__ import annotations

import struct
from collections.abc import Callable

# Minimum run length to encode as RLE (shorter runs use raw encoding)
_MIN_RUN_LENGTH = 3

# Mode flags
_MODE_RAW = 0x00
_MODE_RLE = 0x01


def compress_string_rle(string: str) -> bytes:
    """Compress a string using run-length encoding with hybrid mode.

    Format:
        [segment_count:varint][segments...]

    Each segment:
        [mode:1 byte][length:varint][data]

    Mode = 0x00 (raw): data is raw bytes
    Mode = 0x01 (RLE): data is [char:1 byte][count:varint] pairs

    :param string: String to compress
    :return: Compressed bytes
    """
    if not string:
        return b"\x00"  # Zero segments

    from pygfa.encoding.integer_list_encoding import compress_integer_list_varint

    data = string.encode("ascii")
    segments: list[tuple[int, bytes]] = []  # (mode, data) pairs

    i = 0
    while i < len(data):
        # Count run length
        run_start = i
        current_char = data[i]
        run_length = 1

        while i + run_length < len(data) and data[i + run_length] == current_char:
            run_length += 1

        # Decide whether to encode as RLE or raw
        if run_length >= _MIN_RUN_LENGTH:
            # RLE segment: [char:1 byte][count:varint]
            rle_data = bytes([current_char]) + compress_integer_list_varint([run_length])
            segments.append((_MODE_RLE, rle_data))
            i += run_length
        else:
            # Collect raw bytes until we hit another run
            raw_start = i
            raw_bytes = bytearray()

            while i < len(data):
                # Look ahead for runs
                look_run = 1
                if i + 1 < len(data):
                    while (
                        i + look_run < len(data) and data[i + look_run] == data[i]
                    ):
                        look_run += 1

                if look_run >= _MIN_RUN_LENGTH:
                    # Found a run, stop collecting raw bytes
                    break

                raw_bytes.append(data[i])
                i += 1

            if raw_bytes:
                segments.append((_MODE_RAW, bytes(raw_bytes)))

    # Encode segments
    result = bytearray()
    result.extend(compress_integer_list_varint([len(segments)]))

    for mode, segment_data in segments:
        result.append(mode)
        result.extend(compress_integer_list_varint([len(segment_data)]))
        result.extend(segment_data)

    return bytes(result)


def decompress_string_rle(data: bytes, lengths: list[int]) -> list[bytes]:
    """Decompress RLE-encoded strings.

    :param data: Compressed data
    :param lengths: List of original string lengths
    :return: List of decompressed byte sequences
    """
    if not data or not lengths:
        return []

    from pygfa.bgfa import decode_integer_list_varint

    offset = 0
    results: list[bytes] = []

    for expected_length in lengths:
        if expected_length == 0:
            results.append(b"")
            continue

        # Read segment count
        segment_counts, bytes_used = decode_integer_list_varint(data[offset:], 1)
        segment_count = segment_counts[0]
        offset += bytes_used

        # Decode segments
        decoded = bytearray()
        for _ in range(segment_count):
            # Read mode
            mode = data[offset]
            offset += 1

            # Read segment length
            lengths_list, bytes_used = decode_integer_list_varint(data[offset:], 1)
            segment_length = lengths_list[0]
            offset += bytes_used

            # Read segment data
            segment_data = data[offset : offset + segment_length]
            offset += segment_length

            if mode == _MODE_RAW:
                # Raw bytes
                decoded.extend(segment_data)
            elif mode == _MODE_RLE:
                # RLE: [char:1 byte][count:varint]
                seg_offset = 0
                while seg_offset < len(segment_data):
                    char = segment_data[seg_offset]
                    seg_offset += 1

                    counts, bytes_used = decode_integer_list_varint(
                        segment_data[seg_offset:], 1
                    )
                    count = counts[0]
                    seg_offset += bytes_used

                    decoded.extend([char] * count)
            else:
                raise ValueError(f"Unknown RLE mode: {mode:#x}")

        results.append(bytes(decoded))

    return results


def compress_string_list_rle(
    string_list: list[str],
    compress_integer_list: Callable[[list[int]], bytes] | None = None,
) -> bytes:
    """Compress a list of strings using run-length encoding.

    :param string_list: List of strings
    :param compress_integer_list: Integer list compression function (unused, for API compatibility)
    :return: Compressed bytes with length prefix
    """
    if not string_list:
        return b""

    from pygfa.encoding.integer_list_encoding import compress_integer_list_varint

    # Encode lengths
    lengths = [len(s) for s in string_list]
    length_bytes = compress_integer_list_varint(lengths)

    # Encode each string
    compressed_sequences = [compress_string_rle(s) for s in string_list]

    # Concatenate: [lengths][sequences]
    return length_bytes + b"".join(compressed_sequences)
