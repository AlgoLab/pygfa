from pygfa.encoding.string_encoding import compress_string_list_superstring_ppm
from pygfa.bgfa import decompress_string_superstring_ppm, decode_integer_list_varint
import pytest


def test_superstring_ppm_basic():
    strings = ["GATTACAGA", "GATTACA", "TACAG"]
    compressed = compress_string_list_superstring_ppm(strings)
    decompressed = decompress_string_superstring_ppm(compressed, len(strings), decode_integer_list_varint)
    assert decompressed == [s.encode("ascii") for s in strings]


def test_superstring_ppm_single():
    strings = ["ACGT"]
    compressed = compress_string_list_superstring_ppm(strings)
    decompressed = decompress_string_superstring_ppm(compressed, len(strings), decode_integer_list_varint)
    assert decompressed == [s.encode("ascii") for s in strings]


def test_superstring_ppm_repeated():
    strings = ["AAA", "AAAA", "AA"]
    compressed = compress_string_list_superstring_ppm(strings)
    decompressed = decompress_string_superstring_ppm(compressed, len(strings), decode_integer_list_varint)
    assert decompressed == [s.encode("ascii") for s in strings]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
