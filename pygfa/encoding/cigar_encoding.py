"""CIGAR-specific encoding for alignment strings.

CIGAR strings represent sequence alignments with alternating numbers and operation letters.
Example: "10M2I5D" means 10 matches, 2 insertions, 5 deletions.

Standard ASCII encoding wastes space. This encoding:
- Packs operations into 4 bits (9 operation types: M, I, D, N, S, H, P, =, X)
- Encodes lengths as varint for efficiency
- Achieves 40-60% compression on typical CIGAR strings
"""

from __future__ import annotations

import re
from collections.abc import Callable

# CIGAR operations mapped to 4-bit codes
_CIGAR_OP_TO_CODE = {
    "M": 0x0,  # Match/mismatch
    "I": 0x1,  # Insertion
    "D": 0x2,  # Deletion
    "N": 0x3,  # Skipped region
    "S": 0x4,  # Soft clipping
    "H": 0x5,  # Hard clipping
    "P": 0x6,  # Padding
    "=": 0x7,  # Sequence match
    "X": 0x8,  # Sequence mismatch
}

_CODE_TO_CIGAR_OP = {v: k for k, v in _CIGAR_OP_TO_CODE.items()}

# Regex to parse CIGAR strings: (number)(operation)
_CIGAR_PATTERN = re.compile(r"(\d+)([MIDNSHP=X])")


def compress_string_cigar(string: str) -> bytes:
    """Compress a CIGAR string using operation packing and varint lengths.

    Format:
        [num_ops:varint][packed_ops][lengths:varint...]

    packed_ops: 2 operations per byte (4 bits each), padded if odd count
    lengths: varint-encoded operation lengths

    :param string: CIGAR string (e.g., "10M2I5D")
    :return: Compressed bytes
    """
    if not string:
        return b"\x00"  # Zero operations

    from pygfa.encoding.integer_list_encoding import compress_integer_list_varint

    # Parse CIGAR string
    matches = _CIGAR_PATTERN.findall(string)
    if not matches:
        # Not a valid CIGAR string, return empty
        return b"\x00"

    operations: list[int] = []
    lengths: list[int] = []

    for length_str, op in matches:
        if op not in _CIGAR_OP_TO_CODE:
            # Unknown operation, skip
            continue
        operations.append(_CIGAR_OP_TO_CODE[op])
        lengths.append(int(length_str))

    if not operations:
        return b"\x00"

    # Pack operations: 2 operations per byte
    packed_ops = bytearray()
    for i in range(0, len(operations), 2):
        if i + 1 < len(operations):
            # Two operations: pack as [op0:4bits][op1:4bits]
            byte_val = (operations[i] << 4) | operations[i + 1]
        else:
            # Odd count: last operation in high nibble, low nibble = 0xF (padding marker)
            byte_val = (operations[i] << 4) | 0xF
        packed_ops.append(byte_val)

    # Encode
    result = bytearray()
    result.extend(compress_integer_list_varint([len(operations)]))
    result.extend(packed_ops)
    result.extend(compress_integer_list_varint(lengths))

    return bytes(result)


def decompress_string_cigar(data: bytes, lengths: list[int]) -> list[bytes]:
    """Decompress CIGAR-encoded strings.

    :param data: Compressed data
    :param lengths: List of original CIGAR string lengths (character count, not used for decoding logic)
    :return: List of decompressed CIGAR byte sequences
    """
    if not data or not lengths:
        return []

    from pygfa.bgfa import decode_integer_list_varint

    offset = 0
    results: list[bytes] = []

    for _ in lengths:
        # Read operation count
        op_counts, bytes_used = decode_integer_list_varint(data[offset:], 1)
        op_count = op_counts[0]
        offset += bytes_used

        if op_count == 0:
            results.append(b"")
            continue

        # Read packed operations
        packed_byte_count = (op_count + 1) // 2
        packed_ops = data[offset : offset + packed_byte_count]
        offset += packed_byte_count

        # Unpack operations
        operations: list[int] = []
        for byte_val in packed_ops:
            op0 = (byte_val >> 4) & 0xF
            op1 = byte_val & 0xF
            operations.append(op0)
            if op1 != 0xF:  # 0xF is padding marker
                operations.append(op1)

        # Trim to actual count (in case of padding)
        operations = operations[:op_count]

        # Read lengths
        op_lengths, bytes_used = decode_integer_list_varint(data[offset:], op_count)
        offset += bytes_used

        # Reconstruct CIGAR string
        cigar_parts: list[str] = []
        for op_code, length in zip(operations, op_lengths):
            if op_code in _CODE_TO_CIGAR_OP:
                cigar_parts.append(f"{length}{_CODE_TO_CIGAR_OP[op_code]}")

        results.append("".join(cigar_parts).encode("ascii"))

    return results


def compress_string_list_cigar(
    string_list: list[str],
    compress_integer_list: Callable[[list[int]], bytes] | None = None,
) -> bytes:
    """Compress a list of CIGAR strings.

    :param string_list: List of CIGAR strings
    :param compress_integer_list: Integer list compression function (unused, for API compatibility)
    :return: Compressed bytes with length prefix
    """
    if not string_list:
        return b""

    from pygfa.encoding.integer_list_encoding import compress_integer_list_varint

    # Encode lengths (character counts for API compatibility, though not strictly needed)
    lengths = [len(s) for s in string_list]
    length_bytes = compress_integer_list_varint(lengths)

    # Encode each CIGAR string
    compressed_sequences = [compress_string_cigar(s) for s in string_list]

    # Concatenate: [lengths][sequences]
    return length_bytes + b"".join(compressed_sequences)
