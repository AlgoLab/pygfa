import sys
import os

# Add src to path
sys.path.append(os.getcwd())

from pygfa.encoding.string_encoding import compress_string_list_superstring_none
from pygfa.bgfa import decompress_string_superstring_none, decode_integer_list_varint
import struct


def test_superstring_none():
    strings = ["AAAA", "AAAB", "AAAC"]
    # Expect superstring "AAAABAAAC" or similar greedy result
    # Overlap AAAA, AAAB -> 3 (AAA) -> AAAAB
    # Overlap AAAAB, AAAC -> 3 (AAA) -> AAAABC (Wait, AAAB and AAAC overlap is AA?)

    # greedy_scs logic:
    # Candidates: AAAA, AAAB, AAAC
    # Pairs:
    # AAAA, AAAB -> overlap 3 (AAA) -> merged: AAAAB
    # AAAA, AAAC -> overlap 3 (AAA) -> merged: AAAAC
    # AAAB, AAAC -> overlap 2 (AA) -> merged: AAABAC

    # Best overlap 3.
    # Merge AAAA, AAAB -> AAAAB
    # Candidates: AAAAB, AAAC
    # AAAAB, AAAC -> overlap 2 (AA) -> merged: AAAABAC
    # AAAC, AAAAB -> overlap 0 -> merged: AAACAAAAB

    # Result should be AAAABAC?
    # Strings: AAAA, AAAB, AAAC
    # AAAABAC contains:
    # AAAA at 0
    # AAAB at 1
    # AAAC at ? No, AAAC is not in AAAABAC. A-A-A-B-A-C.
    # AAAC needs AAAC.
    # AAAABAC has AAAAB and ABAC.

    # Let's see what greedy_scs produces.

    compressed = compress_string_list_superstring_none(strings)

    print(f"Compressed size: {len(compressed)}")

    # Check format manually
    # [encoded_superstring_len:uint32] [uncompressed_superstring_len:uint32] [encoded_superstring] [start_indices]

    encoded_len, uncompressed_len = struct.unpack_from("<II", compressed, 0)
    print(f"Encoded len: {encoded_len}, Uncompressed len: {uncompressed_len}")

    superstring = compressed[8 : 8 + encoded_len]
    print(f"Superstring: {superstring}")

    decompressed = decompress_string_superstring_none(compressed, len(strings), decode_integer_list_varint)

    print(f"Decompressed: {decompressed}")

    assert decompressed == [s.encode("ascii") for s in strings]
    print("Test passed!")


if __name__ == "__main__":
    test_superstring_none()
