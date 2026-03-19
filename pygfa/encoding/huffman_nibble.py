"""Nibble-level Canonical Huffman encoding.

This module implements the specialized Huffman encoding defined in the BGFA spec:
1.  Symbols are 4-bit nibbles (16 possible values).
2.  Canonical codes are reconstructed from bit-lengths.
3.  Bitstream is packed MSB-first.
"""

from __future__ import annotations
import struct
from collections import Counter
import heapq


def _get_huffman_lengths(data: bytes) -> list[int]:
    """Compute Huffman bit-lengths for nibbles in data using a correct Huffman tree."""
    if not data:
        return [0] * 16

    nibbles = []
    for b in data:
        nibbles.append((b >> 4) & 0x0F)
        nibbles.append(b & 0x0F)

    counts = Counter(nibbles)
    if not counts:
        return [0] * 16

    # heap stores (frequency, sequence_id, symbol_or_tuple)
    # sequence_id is used to break ties between equal frequencies
    counter = 0
    heap = [[count, counter, sym] for sym, count in counts.items()]
    counter += 1
    heapq.heapify(heap)

    if len(heap) == 1:
        sym = heap[0][2]
        lengths = [0] * 16
        lengths[sym] = 1
        return lengths

    while len(heap) > 1:
        lo = heapq.heappop(heap)
        hi = heapq.heappop(heap)
        # Store sub-nodes as tuples to distinguish from symbols
        node = [lo[0] + hi[0], counter, (lo[2], hi[2])]
        counter += 1
        heapq.heappush(heap, node)

    lengths = [0] * 16

    def traverse(node, depth):
        if isinstance(node, int):
            lengths[node] = depth
        else:
            traverse(node[0], depth + 1)
            traverse(node[1], depth + 1)

    traverse(heap[0][2], 0)
    return lengths


def _build_canonical_codes(lengths: list[int]) -> dict[int, tuple[int, int]]:
    """Build canonical Huffman codes from bit-lengths."""
    sorted_lengths = sorted([(length, i) for i, length in enumerate(lengths) if length > 0])

    if not sorted_lengths:
        return {}

    codes = {}
    current_code = 0
    prev_len = sorted_lengths[0][0]

    for length, sym in sorted_lengths:
        current_code <<= length - prev_len
        codes[sym] = (current_code, length)
        current_code += 1
        prev_len = length

    return codes


def compress_nibble_huffman(data: bytes, int_encoder: callable, first_byte_strategy: int) -> bytes:
    """Compress data using nibble-level Canonical Huffman."""
    if not data:
        return struct.pack("<I", 0)

    lengths = _get_huffman_lengths(data)
    codebook_bytes = int_encoder(lengths)

    codes = _build_canonical_codes(lengths)

    bitstream = []
    for b in data:
        for nibble in [(b >> 4) & 0x0F, b & 0x0F]:
            code_val, bit_len = codes[nibble]
            for i in range(bit_len - 1, -1, -1):
                bitstream.append((code_val >> i) & 1)

    packed_bytes = bytearray()
    for i in range(0, len(bitstream), 8):
        byte_val = 0
        for j in range(8):
            if i + j < len(bitstream):
                byte_val = (byte_val << 1) | bitstream[i + j]
            else:
                byte_val <<= 1
        packed_bytes.append(byte_val)

    return struct.pack("<I", len(codebook_bytes)) + codebook_bytes + bytes(packed_bytes)


def decompress_nibble_huffman(payload: bytes, int_decoder: callable, num_nibbles: int) -> bytes:
    """Decompress nibble-level Canonical Huffman."""
    if not payload or num_nibbles == 0:
        return b""

    codebook_len = struct.unpack_from("<I", payload, 0)[0]
    pos = 4

    codebook_data = payload[pos : pos + codebook_len]
    pos += codebook_len

    lengths, _ = int_decoder(codebook_data, 16)
    codes = _build_canonical_codes(lengths)

    decode_table = {(bits, val): sym for sym, (val, bits) in codes.items()}

    bitstream = payload[pos:]
    decoded_nibbles = []

    current_bits = 0
    current_len = 0
    bit_idx = 0

    while len(decoded_nibbles) < num_nibbles:
        if bit_idx >= len(bitstream) * 8:
            break

        byte_val = bitstream[bit_idx // 8]
        bit = (byte_val >> (7 - (bit_idx % 8))) & 1
        bit_idx += 1

        current_bits = (current_bits << 1) | bit
        current_len += 1

        if (current_len, current_bits) in decode_table:
            decoded_nibbles.append(decode_table[(current_len, current_bits)])
            current_bits = 0
            current_len = 0

    result = bytearray()
    for i in range(0, len(decoded_nibbles), 2):
        hi = decoded_nibbles[i]
        lo = decoded_nibbles[i + 1] if i + 1 < len(decoded_nibbles) else 0
        result.append((hi << 4) | lo)

    return bytes(result)
