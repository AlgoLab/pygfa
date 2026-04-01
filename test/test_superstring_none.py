import os
import sys

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from pygfa.encoding.string_encoding import compress_string_list_superstring_none  # noqa: E402
from pygfa.bgfa import decompress_string_superstring_none  # noqa: E402
import struct  # noqa: E402


def test_superstring_none():
    strings = ["AAAA", "AAAB", "AAAC"]

    compressed = compress_string_list_superstring_none(strings)

    print(f"Compressed size: {len(compressed)}")

    encoded_len, uncompressed_len = struct.unpack_from("<II", compressed, 0)
    print(f"Encoded len: {encoded_len}, Uncompressed len: {uncompressed_len}")

    superstring = compressed[8 : 8 + encoded_len]
    print(f"Superstring: {superstring}")

    decompressed = decompress_string_superstring_none(compressed, [len(s) for s in strings])

    print(f"Decompressed: {decompressed}")

    assert decompressed == [s.encode("ascii") for s in strings]
    print("Test passed!")


if __name__ == "__main__":
    test_superstring_none()
