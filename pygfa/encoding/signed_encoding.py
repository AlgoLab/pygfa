"""Signed integer encoding.

Encodes signed integers as: sign bits (run-length encoded as varint) +
absolute values (using the specified unsigned integer encoder).
"""

from __future__ import annotations

from collections.abc import Callable


def _encode_varint(value: int) -> bytearray:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value == 0:
            out.append(byte)
            break
        else:
            out.append(byte | 0x80)
    return out


def compress_signed_integers(values: list[int], encoder: Callable[..., bytes]) -> bytes:
    """Encode signed integers as sign bits (RLE varint) + abs values.

    Args:
        values: List of signed integers
        encoder: Unsigned integer encoder function (e.g., compress_integer_list_varint)

    Returns:
        Encoded bytes: [RLE varint sign bits][unsigned encoded abs values]
    """
    if not values:
        return b""

    rle_data = bytearray()
    i = 0
    n = len(values)

    if values[0] >= 0:
        run_len = 0
        while i < n and values[i] >= 0:
            i += 1
            run_len += 1
        rle_data.extend(_encode_varint(run_len))
    else:
        rle_data.extend(_encode_varint(0))
        run_len = 0
        while i < n and values[i] < 0:
            i += 1
            run_len += 1
        rle_data.extend(_encode_varint(run_len - 1))

    while i < n:
        current_bit = 1 if values[i] < 0 else 0
        run_len = 0
        while i < n and (values[i] < 0) == current_bit:
            i += 1
            run_len += 1
        rle_data.extend(_encode_varint(run_len - 1))

    abs_values = [abs(v) for v in values]
    abs_payload = encoder(abs_values)
    return bytes(rle_data) + abs_payload


def decode_signed_integers(
    data: bytes, count: int, decoder: Callable[..., tuple[list[int], int]]
) -> tuple[list[int], int]:
    """Decode signed integers from sign bits (RLE varint) + abs values.

    Args:
        data: Encoded bytes
        count: Number of integers to decode
        decoder: Unsigned integer decoder function

    Returns:
        Tuple of (decoded signed integers, bytes consumed)
    """
    if count == 0:
        return [], 0

    pos = 0
    sign_bits = bytearray()
    current_bit = 0

    while len(sign_bits) < count and pos < len(data):
        value = 0
        shift = 0
        while pos < len(data):
            byte = data[pos]
            pos += 1
            value |= (byte & 0x7F) << shift
            shift += 7
            if (byte & 0x80) == 0:
                break

        if not sign_bits and value == 0:
            # Special case: starts with negatives
            if pos >= len(data):
                break
            value = 0
            shift = 0
            while pos < len(data):
                byte = data[pos]
                pos += 1
                value |= (byte & 0x7F) << shift
                shift += 7
                if (byte & 0x80) == 0:
                    break
            run_len = value + 1
            sign_bits.extend(bytearray(b'\x01') * run_len)
            current_bit = 0
        elif not sign_bits:
            run_len = value
            sign_bits.extend(b'\x00' * run_len)
            current_bit = 1
        else:
            run_len = value + 1
            sign_bits.extend(bytearray([current_bit]) * run_len)
            current_bit = 1 - current_bit

    sign_bits = sign_bits[:count]

    abs_values, abs_consumed = decoder(data[pos:], count)

    result = [abs_values[i] if sign_bits[i] == 0 else -abs_values[i] for i in range(count)]
    total_consumed = pos + abs_consumed
    return result, total_consumed
