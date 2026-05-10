from __future__ import annotations

import math
import struct
from collections.abc import Callable, Iterable


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


def compress_integer_list_uints_delta(int_list: Iterable[int], encoder: Callable = None) -> bytes:
    values = list(int_list)
    if not values:
        return b""

    if encoder is None:
        encoder = compress_integer_list_varint

    deltas = [values[0]]
    for i in range(1, len(values)):
        deltas.append(values[i] - values[i - 1])

    from pygfa.encoding.signed_encoding import compress_signed_integers

    return compress_signed_integers(deltas, encoder)


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


def compress_integer_list_golomb(int_list: Iterable[int], _size: int = 0) -> bytes:
    """Encode integers using Golomb coding (bit-level).

    Format per value n:
      - quotient q = n // b, written in unary (q ones, then a zero)
      - remainder r = n % b, written in ceil(log2(b)) bits (MSB first)
    """
    int_list = list(int_list)
    if not int_list:
        return b""
    b = int(max(1, math.sqrt(max(int_list) / len(int_list)))) or 1
    bits_for_remainder = math.ceil(math.log2(b)) if b > 1 else 1

    out = bytes([b])
    bit_buf = 0
    bit_pos = 0

    def write_bit(bit_val: int) -> None:
        nonlocal out, bit_buf, bit_pos
        bit_buf = (bit_buf << 1) | bit_val
        bit_pos += 1
        if bit_pos == 8:
            out += bytes([bit_buf])
            bit_buf = 0
            bit_pos = 0

    for n in int_list:
        quotient, remainder = divmod(n, b)
        for _ in range(quotient):
            write_bit(1)
        write_bit(0)
        for i in range(bits_for_remainder - 1, -1, -1):
            write_bit((remainder >> i) & 1)

    if bit_pos > 0:
        out += bytes([bit_buf << (8 - bit_pos)])

    return out


def compress_integer_list_rice(int_list: Iterable[int], size: int = 4) -> bytes:
    """Encode integers using Rice coding (bit-level).

    Rice coding is Golomb with b as a power of 2: b = 2^k.

    Format per value n:
      - quotient q = n >> k, written in unary (q ones, then a zero)
      - remainder r = n & (2^k - 1), written in k bits (MSB first)
    """
    k = max(0, size)
    b = 1 << k

    out = bytes([k])
    bit_buf = 0
    bit_pos = 0

    def write_bit(bit_val: int) -> None:
        nonlocal out, bit_buf, bit_pos
        bit_buf = (bit_buf << 1) | bit_val
        bit_pos += 1
        if bit_pos == 8:
            out += bytes([bit_buf])
            bit_buf = 0
            bit_pos = 0

    for n in int_list:
        quotient, remainder = divmod(n, b)
        for _ in range(quotient):
            write_bit(1)
        write_bit(0)
        for i in range(k - 1, -1, -1):
            write_bit((remainder >> i) & 1)

    if bit_pos > 0:
        out += bytes([bit_buf << (8 - bit_pos)])

    return out


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
    """Compress a list of integers using VByte encoding.

    VByte encoding uses 7 bits per byte for data, with the high bit as a
    continuation flag. Values < 128 are encoded as single bytes. Larger
    values use multiple bytes with the high bit set on all but the last.

    :param int_list: List of integers to encode
    :param _size: Unused parameter (for API compatibility)
    :return: VByte-encoded bytes
    """
    out = bytearray()
    for val in int_list:
        if val < 0x80:
            out.append(val)
        else:
            num_bytes = 1
            temp = val
            while temp >= 0x80:
                num_bytes += 1
                temp >>= 7
            for i in range(num_bytes):
                if i < num_bytes - 1:
                    out.append((val & 0x7F) | 0x80)
                else:
                    out.append(val & 0x7F)
                val >>= 7
    return bytes(out)


# =============================================================================
# Integer Decoders
# =============================================================================


def decode_integer_list_none(data: bytes, count: int) -> tuple[list[int], int]:
    result = []
    pos = 0
    current = bytearray()

    while pos < len(data):
        byte = data[pos]
        if byte == ord(","):
            if current:
                result.append(int(current.decode("ascii")))
                current = bytearray()
            pos += 1
            if count > 0 and len(result) >= count:
                break
        elif ord("0") <= byte <= ord("9"):
            current.append(byte)
            pos += 1
        else:
            break

    if current:
        result.append(int(current.decode("ascii")))

    if pos < len(data) and data[pos] == ord(","):
        pos += 1

    return result, pos


def decode_integer_list_varint(data: bytes, count: int) -> tuple[list[int], int]:
    result = []
    pos = 0

    while pos < len(data) and (count < 0 or len(result) < count):
        value = 0
        shift = 0
        while pos < len(data):
            byte = data[pos]
            pos += 1
            value |= (byte & 0x7F) << shift
            shift += 7
            if (byte & 0x80) == 0:
                break
        result.append(value)

    return result, pos


def decode_integer_list_fixed16(data: bytes, count: int) -> tuple[list[int], int]:
    n = len(data) // 2 if count < 0 else count
    result = []
    pos = 0

    for _ in range(n):
        if pos + 2 > len(data):
            break
        result.append(struct.unpack_from("<H", data, pos)[0])
        pos += 2

    return result, pos


def decode_integer_list_fixed32(data: bytes, count: int) -> tuple[list[int], int]:
    n = len(data) // 4 if count < 0 else count
    result = []
    pos = 0

    for _ in range(n):
        if pos + 4 > len(data):
            break
        result.append(struct.unpack_from("<I", data, pos)[0])
        pos += 4

    return result, pos


def decode_integer_list_fixed64(data: bytes, count: int) -> tuple[list[int], int]:
    n = len(data) // 8 if count < 0 else count
    result = []
    pos = 0

    for _ in range(n):
        if pos + 8 > len(data):
            break
        result.append(struct.unpack_from("<Q", data, pos)[0])
        pos += 8

    return result, pos


def decode_integer_list_uints_delta(data: bytes, count: int, decoder: Callable = None) -> tuple[list[int], int]:
    if count == 0 or not data:
        return [], 0

    if decoder is None:
        decoder = decode_integer_list_varint

    from pygfa.encoding.signed_encoding import decode_signed_integers

    deltas, consumed = decode_signed_integers(data, count, decoder)

    result = [deltas[0]]
    for i in range(1, len(deltas)):
        result.append(result[-1] + deltas[i])

    return result, consumed


def decode_integer_list_elias_gamma(data: bytes, count: int) -> tuple[list[int], int]:
    if not data:
        return [], 0

    result = []
    bit_pos = 0

    def read_bit() -> int | None:
        nonlocal bit_pos
        if bit_pos >= len(data) * 8:
            return None
        byte_idx = bit_pos // 8
        bit_idx = bit_pos % 8
        bit_pos += 1
        return (data[byte_idx] >> (7 - bit_idx)) & 1

    def read_bits(n: int) -> int:
        val = 0
        for _ in range(n):
            bit = read_bit()
            if bit is None:
                break
            val = (val << 1) | bit
        return val

    while count < 0 or len(result) < count:
        unary = 0
        while True:
            bit = read_bit()
            if bit is None:
                break
            if bit == 0:
                break
            unary += 1

        if unary == 0:
            result.append(0)
        else:
            binary_part = read_bits(unary)
            value = (1 << unary) | binary_part
            result.append(value - 1)

        if bit_pos >= len(data) * 8:
            break

    return result, (bit_pos + 7) // 8


def decode_integer_list_elias_omega(data: bytes, count: int) -> tuple[list[int], int]:
    if not data:
        return [], 0

    result = []
    bit_pos = 0

    def read_bit() -> int | None:
        nonlocal bit_pos
        if bit_pos >= len(data) * 8:
            return None
        byte_idx = bit_pos // 8
        bit_idx = bit_pos % 8
        bit_pos += 1
        return (data[byte_idx] >> (7 - bit_idx)) & 1

    def decode_omega_recursive() -> int:
        bit = read_bit()
        if bit is None or bit == 0:
            return 1

        length = decode_omega_recursive()
        value = 1
        for _ in range(length - 1):
            value = (value << 1) | (read_bit() or 0)
        return value

    while count < 0 or len(result) < count:
        if bit_pos >= len(data) * 8:
            break
        value = decode_omega_recursive()
        result.append(value - 1)

    return result, (bit_pos + 7) // 8


def decode_integer_list_golomb(data: bytes, count: int) -> tuple[list[int], int]:
    if not data or len(data) < 1:
        return [], 0

    b = data[0]
    if b == 0:
        b = 128

    result = []
    pos = 1
    bits_read = 0

    def read_bit() -> int | None:
        nonlocal pos, bits_read
        if pos >= len(data):
            return None
        bit = (data[pos] >> (7 - bits_read)) & 1
        bits_read += 1
        if bits_read == 8:
            bits_read = 0
            pos += 1
        return bit

    bits_for_remainder = math.ceil(math.log2(b)) if b > 1 else 1

    while count < 0 or len(result) < count:
        quotient = 0
        while True:
            bit = read_bit()
            if bit is None:
                break
            if bit == 0:
                break
            quotient += 1

        if quotient == 0 and pos >= len(data):
            break

        remainder = 0
        for _ in range(bits_for_remainder):
            bit = read_bit()
            if bit is not None:
                remainder = (remainder << 1) | bit

        value = quotient * b + remainder
        result.append(value)

    bytes_consumed = pos + (1 if bits_read > 0 else 0)
    return result, bytes_consumed


def decode_integer_list_rice(data: bytes, count: int) -> tuple[list[int], int]:
    if not data or len(data) < 1:
        return [], 0

    k = data[0]
    result = []
    pos = 1
    bits_read = 0

    def read_bit() -> int | None:
        nonlocal pos, bits_read
        if pos >= len(data):
            return None
        bit = (data[pos] >> (7 - bits_read)) & 1
        bits_read += 1
        if bits_read == 8:
            bits_read = 0
            pos += 1
        return bit

    while count < 0 or len(result) < count:
        quotient = 0
        while True:
            bit = read_bit()
            if bit is None:
                break
            if bit == 0:
                break
            quotient += 1

        if quotient == 0 and pos >= len(data):
            break

        remainder = 0
        for _ in range(k):
            bit = read_bit()
            if bit is not None:
                remainder = (remainder << 1) | bit

        value = (quotient << k) | remainder
        result.append(value)

    bytes_consumed = pos + (1 if bits_read > 0 else 0)
    return result, bytes_consumed


def decode_integer_list_streamvbyte(data: bytes, count: int) -> tuple[list[int], int]:
    if not data or len(data) < 4:
        return [], 0

    n = struct.unpack_from("<I", data, 0)[0]
    if n == 0:
        return [], 4

    ctrl_count = (n + 3) // 4
    data_start = 4 + ctrl_count

    if len(data) < data_start:
        return [], 4

    result = []
    ctrl_pos = 4
    data_pos = data_start

    while len(result) < n and ctrl_pos < data_start and data_pos < len(data):
        ctrl = data[ctrl_pos]
        ctrl_pos += 1

        for _ in range(4):
            if len(result) >= n or data_pos >= len(data):
                break

            bytes_used = (ctrl & 0x03) + 1
            ctrl >>= 2

            if data_pos + bytes_used > len(data):
                break

            val = 0
            for i in range(bytes_used):
                val |= data[data_pos + i] << (i * 8)
            result.append(val)
            data_pos += bytes_used

    return result, data_pos


def decode_integer_list_vbyte(data: bytes, count: int) -> tuple[list[int], int]:
    if not data:
        return [], 0

    result = []
    pos = 0

    while count < 0 or len(result) < count:
        if pos >= len(data):
            break

        val = 0
        shift = 0
        while pos < len(data):
            byte = data[pos]
            pos += 1
            val |= (byte & 0x7F) << shift
            shift += 7
            if (byte & 0x80) == 0:
                break
        result.append(val)

    return result, pos
