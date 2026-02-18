from __future__ import annotations

import math
from collections.abc import Iterable


def compress_integer_list_varint(int_list: Iterable[int], _size: int = 0) -> bytes:
    encoded_bytes = b""
    for integer in int_list:
        length = integer
        while length > 0:
            byte = length & 0x7F
            length >>= 7
            if length > 0:
                byte |= 0x80
            encoded_bytes += bytes([byte])
    return encoded_bytes


def compress_integer_list_fixed(int_list: Iterable[int], size: int = 32) -> bytes:
    size_bytes = size // 8
    if size < 8 or size != size_bytes * 8:
        raise ValueError(f"Unsupported size: {size}")
    bytes_data = b""
    for integer in int_list:
        bytes_data += integer.to_bytes(size_bytes, byteorder="little", signed=False)
    return bytes_data


def compress_integer_list_none(int_list: Iterable[int], _size: int = 32) -> bytes:
    return b",".join(str(integer).encode("ascii") for integer in int_list)


def compress_integer_list_delta(int_list: Iterable[int], _size: int = 0) -> bytes:
    int_list = list(int_list)
    if not int_list:
        return b""
    deltas = [int_list[0]] + [int_list[i] - int_list[i - 1] for i in range(1, len(int_list))]
    return compress_integer_list_varint(deltas)


def compress_integer_list_elias_gamma(int_list: Iterable[int], _size: int = 0) -> bytes:
    out = []
    for n in int_list:
        n += 1
        length = n.bit_length()
        out.append(bytes([0x80] * (length - 1) + [length - 1]))
        out.append(n.to_bytes((length + 7) // 8, byteorder="big"))
    return b"".join(out)


def compress_integer_list_elias_omega(int_list: Iterable[int], _size: int = 0) -> bytes:
    out = []
    for n in int_list:
        if n == 0:
            out.append(b"\x01")
            continue
        bits = [1]
        while n > 1:
            bits.append(n & 1)
            n >>= 1
        bits.reverse()
        out.append(bytes([0x80] * (len(bits) - 1) + bits))
    return b"".join(out)


def _golomb_encode(n: int, b: int) -> bytes:
    quotient, remainder = divmod(n, b)
    return b"\x80" * quotient + bytes([remainder | (1 if quotient else 0)])


def compress_integer_list_golomb(int_list: Iterable[int], _size: int = 0) -> bytes:
    int_list = list(int_list)
    if not int_list:
        return b""
    b = int(max(1, math.sqrt(max(int_list) / len(int_list)))) or 1
    return bytes([b]) + b"".join(_golomb_encode(n, b) for n in int_list)


def compress_integer_list_rice(int_list: Iterable[int], size: int = 4) -> bytes:
    k = max(0, size)
    b = 1 << k
    out = [bytes([k])]
    for n in int_list:
        quotient, remainder = divmod(n, b)
        out.append(b"\x80" * quotient + bytes([remainder | (1 if quotient else 0)]))
    return b"".join(out)


def compress_integer_list_streamvbyte(int_list: Iterable[int], _size: int = 0) -> bytes:
    int_list = list(int_list)
    if not int_list:
        return b""
    n = len(int_list)
    out = bytearray(4 + n * 4 + ((n + 3) // 4) * 4)
    out[0] = n & 0xFF
    out[1] = (n >> 8) & 0xFF
    out[2] = (n >> 16) & 0xFF
    out[3] = (n >> 24) & 0xFF
    ctrl_idx = 4
    data_idx = 4 + ((n + 3) // 4) * 4
    for i, val in enumerate(int_list):
        if val < 0x80:
            out[ctrl_idx] = 0
            out[data_idx] = val
            data_idx += 1
        elif val < 0x4000:
            out[ctrl_idx] = 1
            out[data_idx] = val & 0xFF
            out[data_idx + 1] = (val >> 8) & 0xFF
            data_idx += 2
        elif val < 0x200000:
            out[ctrl_idx] = 2
            out[data_idx] = val & 0xFF
            out[data_idx + 1] = (val >> 8) & 0xFF
            out[data_idx + 2] = (val >> 16) & 0xFF
            data_idx += 3
        else:
            out[ctrl_idx] = 3
            out[data_idx] = val & 0xFF
            out[data_idx + 1] = (val >> 8) & 0xFF
            out[data_idx + 2] = (val >> 16) & 0xFF
            out[data_idx + 3] = (val >> 24) & 0xFF
            data_idx += 4
        if (i & 3) == 3:
            ctrl_idx += 4
    return bytes(out[:data_idx])


_VBYTE_CTRL = bytes(
    [
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x40,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0x80,
        0xC0,
        0xC0,
        0xC0,
        0xC0,
        0xC0,
        0xC0,
        0xC0,
        0xC0,
        0xC0,
        0xC0,
        0xC0,
        0xC0,
        0xC0,
        0xC0,
        0xC0,
        0xC0,
        0xC0,
        0xC0,
        0xC0,
        0xC0,
        0xC0,
        0xC0,
        0xC0,
        0xC0,
        0xC0,
        0xC0,
        0xC0,
        0xC0,
        0xC0,
        0xC0,
        0xC0,
        0xC0,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
    ]
)


def compress_integer_list_vbyte(int_list: Iterable[int], _size: int = 0) -> bytes:
    out = bytearray()
    for val in int_list:
        if val < 0x40:
            out.append(val)
        elif val < 0x4000:
            out.append(_VBYTE_CTRL[val & 0xFF] | (val & 0x3F))
            out.append(val >> 6)
        elif val < 0x400000:
            out.append(_VBYTE_CTRL[val & 0xFF] | (val & 0x3F))
            out.append(_VBYTE_CTRL[(val >> 8) & 0xFF] | ((val >> 6) & 0x3F))
            out.append(val >> 14)
        else:
            out.append(_VBYTE_CTRL[val & 0xFF] | (val & 0x3F))
            out.append(_VBYTE_CTRL[(val >> 8) & 0xFF] | ((val >> 6) & 0x3F))
            out.append(_VBYTE_CTRL[(val >> 16) & 0xFF] | ((val >> 14) & 0x3F))
            out.append(val >> 22)
    return bytes(out)
