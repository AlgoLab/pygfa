"""CIGAR-specific encoding for alignment strings.

CIGAR strings represent sequence alignments with alternating numbers and operation letters.
Example: "10M2I5D" means 10 matches, 2 insertions, 5 deletions.

This module supports both:
1. 2-byte strategy codes (0x??09) - simple CIGAR encoding
2. 4-byte strategy codes (0x01??????, 0x02??????) - decomposed CIGAR encoding

See spec/gfa_binary_format.md for full specification.
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


def _parse_cigar(string: str) -> tuple[list[int], list[int]]:
    """Parse a CIGAR string into operations and lengths.
    
    :param string: CIGAR string (e.g., "10M2I5D")
    :return: Tuple of (operations as codes, lengths)
    """
    if not string:
        return [], []
    
    matches = _CIGAR_PATTERN.findall(string)
    if not matches:
        return [], []
    
    operations = []
    lengths = []
    
    for length_str, op in matches:
        if op not in _CIGAR_OP_TO_CODE:
            continue
        operations.append(_CIGAR_OP_TO_CODE[op])
        lengths.append(int(length_str))
    
    return operations, lengths


def compress_string_cigar(string: str) -> bytes:
    """Compress a CIGAR string using operation packing and varint lengths.

    Format (2-byte strategy 0x??09):
        [num_ops:varint][packed_ops][lengths:varint...]

    packed_ops: 2 operations per byte (4 bits each), padded if odd count
    lengths: varint-encoded operation lengths

    Special case: '*' (no alignment) is encoded as a single 0xFF byte.

    :param string: CIGAR string (e.g., "10M2I5D" or "*")
    :return: Compressed bytes
    """
    from pygfa.encoding.integer_list_encoding import compress_integer_list_varint
    
    # Special case: '*' means no alignment
    if string == '*':
        return b'\xff'
    
    if not string:
        return b"\x00"  # Zero operations
    
    operations, lengths = _parse_cigar(string)
    
    if not operations:
        # Not a valid CIGAR string, return empty
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
    :param lengths: List of original CIGAR string lengths (character count, for API compatibility)
    :return: List of decompressed CIGAR byte sequences
    
    Special case: A single 0xFF byte represents '*' (no alignment).
    """
    from pygfa.bgfa import decode_integer_list_varint
    
    if not data or not lengths:
        return []
    
    offset = 0
    results = []
    
    for orig_len in lengths:
        # Special case: '*' (no alignment) is encoded as single 0xFF
        if data[offset] == 0xff:
            results.append(b'*')
            offset += 1
            continue
        
        # Read operation count
        op_counts, bytes_used = decode_integer_list_varint(data[offset:], 1)
        if not op_counts:
            break
        op_count = op_counts[0]
        offset += bytes_used
        
        if op_count == 0:
            results.append(b"")
            continue
        
        # Read packed operations
        packed_byte_count = (op_count + 1) // 2
        packed_ops = data[offset:offset + packed_byte_count]
        offset += packed_byte_count
        
        # Unpack operations
        operations = []
        for byte_val in packed_ops:
            op0 = (byte_val >> 4) & 0xF
            op1 = byte_val & 0xF
            operations.append(op0)
            if op1 != 0xF:  # 0xF is padding marker
                operations.append(op1)
        
        # Trim to actual count
        operations = operations[:op_count]
        
        # Read lengths
        op_lengths, bytes_used = decode_integer_list_varint(data[offset:], op_count)
        offset += bytes_used
        
        # Reconstruct CIGAR string
        cigar_parts = []
        for op_code, length in zip(operations, op_lengths):
            if op_code in _CODE_TO_CIGAR_OP:
                cigar_parts.append(f"{length}{_CODE_TO_CIGAR_OP[op_code]}")
        
        results.append("".join(cigar_parts).encode("ascii"))
    
    return results


def compress_string_cigar_decomposed(
    cigar_list: list[str],
    num_ops_encoder: Callable[[list[int]], bytes],
    lengths_encoder: Callable[[list[int]], bytes],
    ops_string_encoder: Callable[[bytes], bytes],
) -> bytes:
    """Compress CIGAR strings using 4-byte strategy 0x01?????? (numOperations+lengths+operations).
    
    Format:
        [num_ops_list encoded][all_lengths encoded][ops_string encoded]
    
    Where:
    - num_ops_list: list of operation counts for each CIGAR string
    - all_lengths: flattened list of all operation lengths
    - ops_string: packed operations (2 per byte) for all CIGAR strings
    
    :param cigar_list: List of CIGAR strings
    :param num_ops_encoder: Encoder for operation counts
    :param lengths_encoder: Encoder for operation lengths
    :param ops_string_encoder: Encoder for packed operations string
    :return: Compressed bytes
    """
    if not cigar_list:
        return b""
    
    all_num_ops = []
    all_lengths = []
    all_packed_ops = bytearray()
    
    for cigar in cigar_list:
        operations, lengths = _parse_cigar(cigar)
        all_num_ops.append(len(operations))
        all_lengths.extend(lengths)
        
        # Pack operations
        for i in range(0, len(operations), 2):
            if i + 1 < len(operations):
                byte_val = (operations[i] << 4) | operations[i + 1]
            else:
                byte_val = (operations[i] << 4) | 0xF
            all_packed_ops.append(byte_val)
    
    # Encode each component
    result = bytearray()
    result.extend(num_ops_encoder(all_num_ops))
    result.extend(lengths_encoder(all_lengths))
    result.extend(ops_string_encoder(bytes(all_packed_ops)))
    
    return bytes(result)


def decompress_string_cigar_decomposed(
    data: bytes,
    num_cigars: int,
    num_ops_decoder: Callable[[bytes, int], tuple[list[int], int]],
    lengths_decoder: Callable[[bytes, int], tuple[list[int], int]],
    ops_string_decoder: Callable[[bytes], bytes],
) -> list[bytes]:
    """Decompress CIGAR strings encoded with 4-byte strategy 0x01??????.
    
    :param data: Compressed data
    :param num_cigars: Number of CIGAR strings to decode
    :param num_ops_decoder: Decoder for operation counts
    :param lengths_decoder: Decoder for operation lengths
    :param ops_string_decoder: Decoder for packed operations string
    :return: List of decompressed CIGAR byte sequences
    """
    if not data or num_cigars == 0:
        return []
    
    offset = 0
    
    # Decode operation counts
    num_ops, consumed = num_ops_decoder(data[offset:], num_cigars)
    offset += consumed
    
    # Decode all lengths
    total_ops = sum(num_ops)
    all_lengths, consumed = lengths_decoder(data[offset:], total_ops)
    offset += consumed
    
    # Decode packed operations
    packed_ops_bytes = ops_string_decoder(data[offset:])
    
    # Unpack operations
    all_operations = []
    for byte_val in packed_ops_bytes:
        op0 = (byte_val >> 4) & 0xF
        op1 = byte_val & 0xF
        all_operations.append(op0)
        if op1 != 0xF:
            all_operations.append(op1)
    
    # Reconstruct CIGAR strings
    results = []
    length_idx = 0
    op_idx = 0
    
    for num_op in num_ops:
        cigar_parts = []
        for _ in range(num_op):
            if op_idx < len(all_operations) and length_idx < len(all_lengths):
                op_code = all_operations[op_idx]
                length = all_lengths[length_idx]
                if op_code in _CODE_TO_CIGAR_OP:
                    cigar_parts.append(f"{length}{_CODE_TO_CIGAR_OP[op_code]}")
                op_idx += 1
                length_idx += 1
        results.append("".join(cigar_parts).encode("ascii"))
    
    return results


def compress_string_list_cigar(
    string_list: list[str],
    compress_integer_list: Callable[[list[int]], bytes] | None = None,
) -> bytes:
    """Compress a list of CIGAR strings (legacy API for 2-byte strategy).

    :param string_list: List of CIGAR strings
    :param compress_integer_list: Integer list compression function (for API compatibility)
    :return: Compressed bytes with length prefix
    """
    from pygfa.encoding.integer_list_encoding import compress_integer_list_varint
    
    if not string_list:
        return b""
    
    # Encode lengths (character counts for API compatibility)
    lengths = [len(s) for s in string_list]
    length_bytes = compress_integer_list_varint(lengths)
    
    # Encode each CIGAR string
    compressed_sequences = [compress_string_cigar(s) for s in string_list]
    
    # Concatenate: [lengths][sequences]
    return length_bytes + b"".join(compressed_sequences)


def compress_cigar_with_strategy(
    cigar_list: list[str],
    strategy_code: int,
) -> bytes:
    """Compress CIGAR strings using the specified strategy code.
    
    Supports both 2-byte (0x??09) and 4-byte (0x01??????, 0x02??????) strategy codes.
    
    :param cigar_list: List of CIGAR strings
    :param strategy_code: Strategy code (2-byte or 4-byte)
    :return: Compressed bytes
    """
    from pygfa.encoding.integer_list_encoding import (
        compress_integer_list_varint,
        compress_integer_list_fixed,
    )
    from pygfa.bgfa import split_4byte_code
    
    # Check if it's a 4-byte strategy (section_id dependent, but we can detect by value)
    # 4-byte codes have decomposition in high byte
    byte1 = (strategy_code >> 24) & 0xFF if strategy_code > 0xFFFF else 0
    
    if byte1 == 0x01:
        # numOperations+lengths+operations decomposition
        b1, b2, b3, b4 = split_4byte_code(strategy_code)

        # Get encoders for each component
        int_enc = b2
        len_enc = b3
        ops_enc = b4

        # Create encoder functions
        if int_enc == 0x01:
            num_ops_encoder = compress_integer_list_varint
        elif int_enc == 0x02:
            def _encode_fixed16(x):
                return compress_integer_list_fixed(x, 16)
            num_ops_encoder = _encode_fixed16
        else:
            num_ops_encoder = compress_integer_list_varint

        if len_enc == 0x01:
            lengths_encoder = compress_integer_list_varint
        elif len_enc == 0x02:
            def _encode_len_fixed16(x):
                return compress_integer_list_fixed(x, 16)
            lengths_encoder = _encode_len_fixed16
        else:
            lengths_encoder = compress_integer_list_varint

        # For ops_string, use the string encoding from b4
        if ops_enc == 0x00:
            def _identity(x):
                return x
            ops_string_encoder = _identity
        elif ops_enc == 0x02:
            import gzip
            ops_string_encoder = gzip.compress
        elif ops_enc == 0x03:
            import lzma
            ops_string_encoder = lzma.compress
        else:
            def _identity_ops(x):
                return x
            ops_string_encoder = _identity_ops

        return compress_string_cigar_decomposed(
            cigar_list, num_ops_encoder, lengths_encoder, ops_string_encoder
        )
    
    elif byte1 == 0x02:
        # String decomposition - treat as plain string with compression
        b1, b2, b3, b4 = split_4byte_code(strategy_code)
        str_enc = b2
        
        # Join with newlines and compress
        joined = "\n".join(cigar_list).encode("ascii")
        
        if str_enc == 0x00:
            return joined
        elif str_enc == 0x01:
            try:
                import compression.zstd as z
                return z.compress(joined)
            except ImportError:
                return joined
        elif str_enc == 0x02:
            import gzip
            return gzip.compress(joined)
        elif str_enc == 0x03:
            import lzma
            return lzma.compress(joined)
        else:
            return joined
    
    else:
        # 2-byte strategy 0x??09 - simple CIGAR encoding
        return compress_string_list_cigar(cigar_list)
