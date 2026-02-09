"""2-bit DNA encoding for efficient sequence compression.

DNA sequences are the largest data component in GFA files. Standard ASCII encoding
uses 8 bits per nucleotide, but DNA has only 4 bases (A, C, G, T), which can be
encoded in 2 bits each, achieving 75% space reduction.

This module provides encoding/decoding for DNA sequences with support for
ambiguity codes (N, R, Y, etc.) via an exception table.
"""

from __future__ import annotations

import struct
from collections.abc import Callable

# 2-bit encoding: A=00, C=01, G=10, T=11
_DNA_TO_2BIT = {
    ord("A"): 0b00,
    ord("a"): 0b00,
    ord("C"): 0b01,
    ord("c"): 0b01,
    ord("G"): 0b10,
    ord("g"): 0b10,
    ord("T"): 0b11,
    ord("t"): 0b11,
    ord("U"): 0b11,  # RNA: Uracil maps to T
    ord("u"): 0b11,
}

_2BIT_TO_DNA = [ord("A"), ord("C"), ord("G"), ord("T")]

# Ambiguity codes that require exception handling
_AMBIGUITY_CODES = set(b"NRYKMSWBDHVnrykmsWbdhv-")


def compress_string_2bit_dna(string: str) -> bytes:
    """Compress a DNA sequence using 2-bit encoding.

    Each nucleotide (A, C, G, T) is encoded in 2 bits, packing 4 bases per byte.
    Ambiguity codes (N, R, Y, etc.) are stored in an exception table.

    Format:
        [flags:1 byte][packed_bases][exception_count:varint][exceptions]

    Flags (1 byte):
        bit 0: has_exceptions (1 if exception table present)
        bits 1-7: reserved

    Each exception: [position:varint][original_byte:1 byte]

    :param string: DNA sequence string
    :return: Compressed bytes
    """
    if not string:
        return b"\x00"

    data = string.encode("ascii")
    exceptions: list[tuple[int, int]] = []
    packed_bits: list[int] = []

    # First pass: identify exceptions and encode standard bases
    for i, byte in enumerate(data):
        if byte in _DNA_TO_2BIT:
            packed_bits.append(_DNA_TO_2BIT[byte])
        elif byte in _AMBIGUITY_CODES:
            exceptions.append((i, byte))
            packed_bits.append(0b00)  # Placeholder: will be replaced during decoding
        else:
            # Unknown character - treat as N
            exceptions.append((i, ord("N")))
            packed_bits.append(0b00)

    # Pack bits into bytes (4 bases per byte)
    packed_bytes = bytearray()
    for i in range(0, len(packed_bits), 4):
        chunk = packed_bits[i : i + 4]
        # Pad last chunk if needed
        while len(chunk) < 4:
            chunk.append(0b00)
        # Pack 4 2-bit values into 1 byte: [base3|base2|base1|base0]
        byte_val = (chunk[0] << 6) | (chunk[1] << 4) | (chunk[2] << 2) | chunk[3]
        packed_bytes.append(byte_val)

    # Build result
    result = bytearray()

    # Flags byte
    has_exceptions = len(exceptions) > 0
    flags = 0x01 if has_exceptions else 0x00
    result.append(flags)

    # Packed bases
    result.extend(packed_bytes)

    # Exception table (if needed)
    if has_exceptions:
        from pygfa.encoding.integer_list_encoding import compress_integer_list_varint

        # Encode exception count
        result.extend(compress_integer_list_varint([len(exceptions)]))

        # Encode exceptions: [position, byte] pairs
        exception_data = []
        for pos, byte in exceptions:
            exception_data.append(pos)
        result.extend(compress_integer_list_varint(exception_data))

        # Append exception bytes
        for _pos, byte in exceptions:
            result.append(byte)

    return bytes(result)


def decompress_string_2bit_dna(data: bytes, lengths: list[int]) -> list[bytes]:
    """Decompress 2-bit encoded DNA sequences.

    This function is designed to work with the BGFA decoder framework where:
    - The BGFA framework extracts lengths from the data first
    - Then passes the remaining data and lengths to this decoder

    However, when used standalone with compress_string_list_2bit_dna output,
    the data includes length prefix that needs to be skipped.

    :param data: Compressed data (may or may not have length prefix)
    :param lengths: List of original sequence lengths
    :return: List of decompressed byte sequences
    """
    if not data or not lengths:
        return []

    from pygfa.bgfa import decode_integer_list_varint

    # Always start at offset 0 - assume BGFA has already extracted lengths
    # (or for standalone use, caller should extract lengths first)
    offset = 0
    results: list[bytes] = []

    for length in lengths:
        if length == 0:
            results.append(b"")
            continue

        # Read flags
        flags = data[offset]
        offset += 1
        has_exceptions = (flags & 0x01) != 0

        # Calculate packed bytes needed
        packed_byte_count = (length + 3) // 4  # Ceiling division
        packed_data = data[offset : offset + packed_byte_count]
        offset += packed_byte_count

        # Unpack 2-bit bases
        unpacked = bytearray()
        for byte_val in packed_data:
            unpacked.append(_2BIT_TO_DNA[(byte_val >> 6) & 0b11])
            unpacked.append(_2BIT_TO_DNA[(byte_val >> 4) & 0b11])
            unpacked.append(_2BIT_TO_DNA[(byte_val >> 2) & 0b11])
            unpacked.append(_2BIT_TO_DNA[byte_val & 0b11])

        # Trim to actual length
        unpacked = unpacked[:length]

        # Apply exceptions if present
        if has_exceptions:
            # Read exception count
            exc_counts, exc_count_bytes_used = decode_integer_list_varint(data[offset:], 1)
            exc_count = exc_counts[0]
            offset += exc_count_bytes_used

            # Read exception positions
            exc_positions, exc_pos_bytes_used = decode_integer_list_varint(
                data[offset:], exc_count
            )
            offset += exc_pos_bytes_used

            # Read exception bytes
            for pos in exc_positions:
                if pos < len(unpacked):
                    unpacked[pos] = data[offset]
                offset += 1

        results.append(bytes(unpacked))

    return results


def compress_string_list_2bit_dna(
    string_list: list[str],
    compress_integer_list: Callable[[list[int]], bytes] | None = None,
) -> bytes:
    """Compress a list of DNA sequences using 2-bit encoding.

    :param string_list: List of DNA sequence strings
    :param compress_integer_list: Integer list compression function (unused, for API compatibility)
    :return: Compressed bytes with length prefix
    """
    if not string_list:
        return b""

    from pygfa.encoding.integer_list_encoding import compress_integer_list_varint

    # Encode lengths
    lengths = [len(s) for s in string_list]
    length_bytes = compress_integer_list_varint(lengths)

    # Encode each sequence
    compressed_sequences = [compress_string_2bit_dna(s) for s in string_list]

    # Concatenate: [lengths][sequences]
    return length_bytes + b"".join(compressed_sequences)
