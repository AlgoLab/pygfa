import compression.zstd as z


def compress_string_zstd(string):
    """Compress a string using zstd compression.

    :param string: The string to compress.
    :returns: The compressed string as bytes.
    """
    return z.compress(string.encode("ascii"), level=19)


def compress_string_gzip(string):
    """Compress a string using gzip compression.

    :param string: The string to compress.
    :returns: The compressed string as bytes.
    """
    import gzip

    return gzip.compress(string.encode("ascii"))


def compress_string_lzma(string):
    """Compress a string using lzma compression.

    :param string: The string to compress.
    :returns: The compressed string as bytes.
    """
    import lzma

    return lzma.compress(string.encode("ascii"))


def compress_string_none(string):
    """Return the input string without compression.

    :param string: The string to return.
    :returns: The input string as bytes.
    """
    return string.encode("ascii")


def compress_string_list(
    string_list,
    compress_integer_list=None,
    compression_method="zstd",
    compression_level=19,
):
    """Compress a list of strings by encoding their lengths and compressing the concatenated strings.

    :param string_list: List of strings to compress.
    :param length_encoding: Method to encode string lengths ('varint', 'fixed32', 'fixed64').
    :param compression_method: The compression method to use ('zstd', 'gzip', 'lzma', 'none').
    :param compression_level: The compression level (1-19 for zstd, 1-9 for gzip/lzma).
    :returns: Compressed data containing encoded lengths followed by compressed strings.
    """

    strings = [string.encode("ascii") for string in string_list]
    length_bytes = compress_integer_list([len(s) for s in strings])

    # Concatenate all strings
    concatenated_strings = b"".join(strings)

    # Compress the concatenated strings
    if compression_method == "zstd":
        compressed_data = z.compress(concatenated_strings, level=compression_level)
    elif compression_method == "gzip":
        import gzip

        compressed_data = gzip.compress(
            concatenated_strings, compresslevel=compression_level
        )
    elif compression_method == "lzma":
        import lzma

        compressed_data = lzma.compress(concatenated_strings, preset=compression_level)
    elif compression_method == "none":
        compressed_data = concatenated_strings
    else:
        raise ValueError(f"Unsupported compression method: {compression_method}")

    # Return concatenated length bytes and compressed data
    return length_bytes + compressed_data
