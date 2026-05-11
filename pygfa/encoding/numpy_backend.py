"""Numpy-accelerated backend for BGFA encoding/decoding operations.

Provides numpy-based alternatives for bulk operations that are
significantly faster than pure-Python equivalents for large datasets.
"""

from __future__ import annotations

import math
from collections.abc import Callable

import numpy as np

# =============================================================================
# Bit-packing (LSB-first within uint64 words)
# =============================================================================


def pack_bits_lsb_numpy(bits: list[int]) -> bytes:
    """Pack bits using numpy, LSB-first within uint64 words.

    Each uint64 word stores 64 bits, with bit i at position i
    LSB-first (bit 0 → bit 0, bit 63 → bit 63).

    :param bits: List of 0/1 values
    :return: Packed bytes (multiple of 8 bytes)
    """
    if not bits:
        return b""

    arr = np.array(bits, dtype=np.uint8)
    n = len(arr)
    padded_len = math.ceil(n / 64) * 64
    if padded_len > n:
        arr = np.pad(arr, (0, padded_len - n), mode="constant")

    words = arr.reshape(-1, 64)
    indices = np.arange(64, dtype=np.uint64)
    word_vals = np.bitwise_or.reduce(words.astype(np.uint64) << indices, axis=1)
    return word_vals.tobytes()


def unpack_bits_lsb_numpy(data: bytes, count: int) -> tuple[list[int], int]:
    """Unpack bits from LSB-first packed uint64 words using numpy.

    :param data: Packed bytes
    :param count: Number of bits to extract
    :return: Tuple of (list of bits, bytes consumed)
    """
    if count == 0:
        return [], 0

    n_words = math.ceil(count / 64)
    bytes_consumed = n_words * 8

    chunk = data[:bytes_consumed]
    words = np.frombuffer(chunk, dtype=np.uint64, count=n_words)

    # Extract bits LSB-first: shift each uint64 by 0..63 and mask LSB
    bits = ((words[:, np.newaxis] >> np.arange(64, dtype=np.uint64)) & 1)
    result = bits.flatten()[:count].tolist()

    return result, bytes_consumed


# =============================================================================
# uints_delta (diff/cumsum via numpy)
# =============================================================================


def uints_delta_encode_numpy(values: list[int], encoder: Callable) -> bytes:
    """Delta-encode integers using numpy diff, then sign-encode.

    :param values: List of unsigned integers (sorted)
    :param encoder: Integer encoder for the delta values
    :return: Encoded bytes
    """
    if not values:
        return b""

    arr = np.array(values, dtype=np.int64)
    deltas = np.zeros(len(values), dtype=np.int64)
    deltas[0] = values[0]
    if len(values) > 1:
        deltas[1:] = arr[1:] - arr[:-1]

    from pygfa.encoding.signed_encoding import compress_signed_integers as py_compress_signed

    return py_compress_signed(deltas.tolist(), encoder)


def uints_delta_decode_numpy(
    data: bytes, count: int, decoder: Callable
) -> tuple[list[int], int]:
    """Decode signed integers, reconstruct using numpy cumsum.

    :param data: Encoded bytes
    :param count: Number of integers to decode
    :param decoder: Unsigned integer decoder function
    :return: Tuple of (decoded unsigned integers, bytes consumed)
    """
    from pygfa.encoding.signed_encoding import decode_signed_integers as py_decode_signed

    signed_values, consumed = py_decode_signed(data, count, decoder)
    if len(signed_values) <= 1:
        return signed_values, consumed

    arr = np.array(signed_values, dtype=np.int64)
    reconstructed = np.cumsum(arr).tolist()
    return reconstructed, consumed


# =============================================================================
# 2-bit DNA encoding (numpy vectorized)
# =============================================================================

# Lookup table: 256 entries, index by uint8 value
_DNA_TO_2BIT_ARRAY = np.zeros(256, dtype=np.uint8)
for c in [ord("A"), ord("a")]:
    _DNA_TO_2BIT_ARRAY[c] = 0
for c in [ord("C"), ord("c")]:
    _DNA_TO_2BIT_ARRAY[c] = 1
for c in [ord("G"), ord("g")]:
    _DNA_TO_2BIT_ARRAY[c] = 2
for c in [ord("T"), ord("t"), ord("U"), ord("u")]:
    _DNA_TO_2BIT_ARRAY[c] = 3

_AMBIGUITY_CODES_SET = set(b"NRYKMSWBDHVnrykmswbdhv-*")
_STANDARD_DNA_CODES = [
    ord("A"),
    ord("a"),
    ord("C"),
    ord("c"),
    ord("G"),
    ord("g"),
    ord("T"),
    ord("t"),
    ord("U"),
    ord("u"),
]


def compress_string_2bit_dna_numpy(data: bytes, int_encoder: Callable | None = None) -> bytes:
    """Numpy-accelerated 2-bit DNA encoding.

    Same wire format as :func:`pygfa.encoding.dna_encoding.compress_string_2bit_dna`.

    :param data: DNA sequence bytes
    :param int_encoder: Integer encoder for exception positions
    :return: Compressed bytes
    """
    if not data:
        return b"\x00"

    arr = np.frombuffer(data, dtype=np.uint8)
    packed_values = _DNA_TO_2BIT_ARRAY[arr]

    # Find non-standard positions
    is_standard = np.isin(arr, _STANDARD_DNA_CODES)
    exception_mask = ~is_standard
    exception_positions = np.where(exception_mask)[0]

    # Pack 4 values per byte: v0<<6 | v1<<4 | v2<<2 | v3
    n = len(packed_values)
    pad = (4 - n % 4) % 4
    if pad:
        padded = np.pad(packed_values, (0, pad), mode="constant")
    else:
        padded = packed_values
    reshaped = padded.reshape(-1, 4)
    packed_bytes = (
        (reshaped[:, 0].astype(np.uint16) << 6)
        | (reshaped[:, 1].astype(np.uint16) << 4)
        | (reshaped[:, 2].astype(np.uint16) << 2)
        | reshaped[:, 3].astype(np.uint16)
    ).astype(np.uint8).tobytes()

    result = bytearray()
    has_exceptions = len(exception_positions) > 0
    result.append(0x01 if has_exceptions else 0x00)
    result.extend(packed_bytes)

    if has_exceptions:
        if int_encoder is None:
            from pygfa.encoding.integer_list_encoding import compress_integer_list_varint

            int_encoder = compress_integer_list_varint
        result.extend(int_encoder([len(exception_positions)]))
        result.extend(int_encoder(exception_positions.tolist()))
        for pos in exception_positions:
            result.append(data[pos])

    return bytes(result)
