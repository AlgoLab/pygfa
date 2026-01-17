from __future__ import annotations

from typing import Iterable


def compress_integer_list_varint(int_list: Iterable[int], size: int = 0) -> bytes:
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


def compress_integer_list_none(int_list: Iterable[int], size: int = 32) -> bytes:
    return b",".join(str(integer).encode("ascii") for integer in int_list)
