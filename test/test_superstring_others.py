import os
import sys

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from pygfa.encoding.string_encoding import (  # noqa: E402
    compress_string_list_superstring_huffman,
    compress_string_list_superstring_2bit,
)
from pygfa.bgfa import (  # noqa: E402
    decompress_string_superstring_huffman,
    decompress_string_superstring_2bit,
    decode_integer_list_varint,
)


def test_superstring_huffman():
    print("Testing Superstring + Huffman...")
    strings = ["GATTACA", "TTACAGA", "CAGAT"]

    compressed = compress_string_list_superstring_huffman(strings)
    print(f"Compressed size: {len(compressed)}")

    decompressed = decompress_string_superstring_huffman(
        compressed, len(strings), decode_integer_list_varint
    )
    print(f"Decompressed: {decompressed}")

    assert decompressed == [s.encode("ascii") for s in strings]
    print("Superstring + Huffman test passed!")


def test_superstring_2bit():
    print("Testing Superstring + 2-bit DNA...")
    strings = ["ACGT", "CGTA", "GTAC"]

    compressed = compress_string_list_superstring_2bit(strings)
    print(f"Compressed size: {len(compressed)}")

    decompressed = decompress_string_superstring_2bit(
        compressed, len(strings), decode_integer_list_varint
    )
    print(f"Decompressed: {decompressed}")

    assert decompressed == [s.encode("ascii") for s in strings]
    print("Superstring + 2-bit DNA test passed!")


if __name__ == "__main__":
    test_superstring_huffman()
    test_superstring_2bit()
