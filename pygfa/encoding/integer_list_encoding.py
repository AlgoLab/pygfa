from __future__ import annotations

import math
from collections.abc import Iterable


def compress_integer_list_varint(int_list: Iterable[int], _size: int = 0) -> bytes:
    out = []
    for integer in int_list:
        value = integer
        while True:
            byte = value & 0x7F
            value >>= 7
            if value == 0:
                out.append(byte)
                break
            else:
                out.append(byte | 0x80)
    return bytes(out)


def compress_integer_list_fixed(int_list: Iterable[int], size: int = 32) -> bytes:
    size_bytes = size // 8
    if size < 8 or size != size_bytes * 8:
        raise ValueError(f"Unsupported size: {size}")
    bytes_data = b""
    for integer in int_list:
        bytes_data += integer.to_bytes(size_bytes, byteorder="little", signed=False)
    return bytes_data


def compress_integer_list_none(int_list: Iterable[int], _size: int = 32) -> bytes:
    int_list = list(int_list)
    if not int_list:
        return b""
    return b",".join(str(integer).encode("ascii") for integer in int_list) + b","


def compress_integer_list_delta(int_list: Iterable[int], _size: int = 0) -> bytes:
    int_list = list(int_list)
    if not int_list:
        return b""

    out = bytearray()
    prev = 0
    for val in int_list:
        delta = val - prev
        if delta >= 0:
            v = delta << 1
        else:
            v = ((-delta - 1) << 1) | 1
        while True:
            byte = v & 0x7F
            v >>= 7
            if v == 0:
                out.append(byte)
                break
            else:
                out.append(byte | 0x80)
        prev = val
    return bytes(out)


def compress_integer_list_elias_gamma(int_list: Iterable[int], _size: int = 0) -> bytes:
    out = []
    for n in int_list:
        n += 1
        length = n.bit_length()
        out.append(bytes([0x80] * (length - 1) + [length - 1]))
        out.append(n.to_bytes((length + 7) // 8, byteorder="big"))
    return b"".join(out)


def compress_integer_list_elias_omega(int_list: Iterable[int], _size: int = 0) -> bytes:
    out = bytearray()
    for n in int_list:
        # Elias omega encoding for non-negative integers.
        # We encode n+1 so that 0 can be represented.
        m = n + 1
        if m == 1:
            # n=0: encode as single 0x01 byte (bit 1)
            out.append(1)
            continue

        # Get binary representation of m (MSB first)
        bits = []
        temp = m
        while temp:
            bits.insert(0, temp & 1)
            temp >>= 1

        # Prepend (len(bits)-1) copies of 0x80
        out.extend([0x80] * (len(bits) - 1))
        # Append bits as bytes (0 or 1)
        out.extend(bits)

    return bytes(out)


def _golomb_encode(n: int, b: int) -> bytes:
    quotient, remainder = divmod(n, b)
    return b"\x80" * quotient + bytes([remainder])


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
        # Leading 0x80 bytes for quotient, then remainder byte
        out.append(b"\x80" * quotient + bytes([remainder]))
    return b"".join(out)


def compress_integer_list_streamvbyte(int_list: Iterable[int], _size: int = 0) -> bytes:
    int_list = list(int_list)
    if not int_list:
        return b""
    n = len(int_list)
    ctrl_count = (n + 3) // 4
    byte_widths = []
    for val in int_list:
        if val < 0x80:
            byte_widths.append(1)
        elif val < 0x4000:
            byte_widths.append(2)
        elif val < 0x200000:
            byte_widths.append(3)
        else:
            byte_widths.append(4)
    total_data = sum(byte_widths)
    data_start = 4 + ctrl_count
    out = bytearray(data_start + total_data)
    out[0] = n & 0xFF
    out[1] = (n >> 8) & 0xFF
    out[2] = (n >> 16) & 0xFF
    out[3] = (n >> 24) & 0xFF
    ctrl_pos = 4
    data_pos = data_start
    for i, val in enumerate(int_list):
        group = i & 3
        if group == 0:
            ctrl_pos = 4 + (i >> 2)
            out[ctrl_pos] = 0
        bw = byte_widths[i]
        out[ctrl_pos] |= (bw - 1) << (group * 2)
        if bw == 1:
            out[data_pos] = val & 0xFF
        elif bw == 2:
            out[data_pos] = val & 0xFF
            out[data_pos + 1] = (val >> 8) & 0xFF
        elif bw == 3:
            out[data_pos] = val & 0xFF
            out[data_pos + 1] = (val >> 8) & 0xFF
            out[data_pos + 2] = (val >> 16) & 0xFF
        else:
            out[data_pos] = val & 0xFF
            out[data_pos + 1] = (val >> 8) & 0xFF
            out[data_pos + 2] = (val >> 16) & 0xFF
            out[data_pos + 3] = (val >> 24) & 0xFF
        data_pos += bw
    return bytes(out)


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
