def compress_integer_list_varint(list, size=0):
    """Use variable-length encoding to compress a list of integers

    :param list: list of integers
    :returns the encoded list.
    """
    encoded_bytes = b""
    for integer in list:
        length = integer
        # Encode length as varint (7-bit chunks)
        while length > 0:
            byte = length & 0x7F
            length >>= 7
            if length > 0:
                byte |= 0x80
            encoded_bytes += bytes([byte])
    return encoded_bytes


def compress_integer_list_fixed(list, size=32):
    """Use a fixed number of bits for each integer

    :param list: list of integers
    :param size: number of bits for each integer
    :returns the encoded list.
    """
    size_bytes = size // 8
    if size < 8 or size != size_bytes * 8:
        raise ValueError(f"Unsupported size: {size}")
    bytes = b""
    for integer in list:
        bytes += integer.to_bytes(size_bytes, byteorder="little", signed=False)
    return bytes


def compress_integer_list_none(list, size=32):
    """Dummy compressor

    Return the concatenation of the textual representation of each integer,
    separated by commas
    :param list: list of integers
    :param size: number of bits for each integer
    :returns the encoded list.
    """
    return b",".join(str(integer).encode("ascii") for integer in list)
