"""2-bit DNA encoding for efficient sequence compression.

DNA sequences are the largest data component in GFA files. Standard ASCII encoding
uses 8 bits per nucleotide, but DNA has only 4 bases (A, C, G, T), which can be
encoded in 2 bits each, achieving 75% space reduction.
"""

from __future__ import annotations
from collections.abc import Callable

# 2-bit encoding: A=00, C=01, G=10, T=11
_DNA_TO_2BIT = {
    ord("A"): 0b00, ord("a"): 0b00,
    ord("C"): 0b01, ord("c"): 0b01,
    ord("G"): 0b10, ord("g"): 0b10,
    ord("T"): 0b11, ord("t"): 0b11,
    ord("U"): 0b11, ord("u"): 0b11,
}

_2BIT_TO_DNA = [ord("A"), ord("C"), ord("G"), ord("T")]
# Ambiguity codes including * (wildcard/no sequence) and - (gap)
_AMBIGUITY_CODES = set(b"NRYKMSWBDHVnrykmswbdhv-*")

def compress_string_2bit_dna(string: str, int_encoder: Callable[[list[int]], bytes] | None = None) -> bytes:
    """Compress a DNA sequence using 2-bit encoding.
    
    Format: [flags:1 byte][packed_bases][exception_count][exception_positions][exception_bytes]
    """
    if int_encoder is None:
        from pygfa.encoding.integer_list_encoding import compress_integer_list_varint
        int_encoder = compress_integer_list_varint

    if not string:
        return b"\x00"

    data = string.encode("ascii")
    exceptions: list[tuple[int, int]] = []
    packed_bits: list[int] = []

    for i, byte in enumerate(data):
        if byte in _DNA_TO_2BIT:
            packed_bits.append(_DNA_TO_2BIT[byte])
        else:
            exceptions.append((i, byte if byte in _AMBIGUITY_CODES else ord("N")))
            packed_bits.append(0b00)

    packed_bytes = bytearray()
    for i in range(0, len(packed_bits), 4):
        chunk = packed_bits[i : i + 4]
        while len(chunk) < 4:
            chunk.append(0b00)
        byte_val = (chunk[0] << 6) | (chunk[1] << 4) | (chunk[2] << 2) | chunk[3]
        packed_bytes.append(byte_val)

    result = bytearray()
    has_exceptions = len(exceptions) > 0
    result.append(0x01 if has_exceptions else 0x00)
    result.extend(packed_bytes)

    if has_exceptions:
        result.extend(int_encoder([len(exceptions)]))
        result.extend(int_encoder([pos for pos, _ in exceptions]))
        for _, byte in exceptions:
            result.append(byte)

    return bytes(result)

def decompress_string_2bit_dna(data: bytes, lengths: list[int], int_decoder: Callable | None = None) -> list[bytes]:
    """Decompress 2-bit encoded DNA sequences.
    """
    if not data or not lengths:
        return []
    if int_decoder is None:
        from pygfa.bgfa import decode_integer_list_varint
        int_decoder = decode_integer_list_varint

    offset = 0
    results: list[bytes] = []

    for length in lengths:
        if length == 0:
            results.append(b"")
            continue

        flags = data[offset]
        offset += 1
        has_exceptions = (flags & 0x01) != 0

        packed_byte_count = (length + 3) // 4
        packed_data = data[offset : offset + packed_byte_count]
        offset += packed_byte_count

        unpacked = bytearray()
        for byte_val in packed_data:
            unpacked.append(_2BIT_TO_DNA[(byte_val >> 6) & 0b11])
            unpacked.append(_2BIT_TO_DNA[(byte_val >> 4) & 0b11])
            unpacked.append(_2BIT_TO_DNA[(byte_val >> 2) & 0b11])
            unpacked.append(_2BIT_TO_DNA[byte_val & 0b11])

        unpacked = unpacked[:length]

        if has_exceptions:
            exc_counts, c1 = int_decoder(data[offset:], 1)
            exc_count = exc_counts[0]
            offset += c1
            exc_positions, c2 = int_decoder(data[offset:], exc_count)
            offset += c2
            for pos in exc_positions:
                if pos < len(unpacked):
                    unpacked[pos] = data[offset]
                offset += 1

        results.append(bytes(unpacked))

    return results

def compress_string_list_2bit_dna(string_list: list[str], int_encoder: Callable | None = None) -> bytes:
    if not string_list:
        return b""
    if int_encoder is None:
        from pygfa.encoding.integer_list_encoding import compress_integer_list_varint
        int_encoder = compress_integer_list_varint
    lengths = [len(s) for s in string_list]
    res = int_encoder(lengths)
    for s in string_list:
        res += compress_string_2bit_dna(s, int_encoder)
    return res
