"""Test round-trip for 4-byte CIGAR decomposition codec."""

import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pygfa.encoding.cigar_encoding import (
    compress_string_cigar_decomposed,
    decompress_string_cigar_decomposed,
)
from pygfa.bgfa import (
    decode_integer_list_varint,
)
from pygfa.encoding.integer_list_encoding import (
    compress_integer_list_varint,
)


class TestCigarDecomposed(unittest.TestCase):
    """Test 4-byte CIGAR decomposition encoding and decoding."""

    def test_roundtrip_basic_varint(self):
        """Test basic round-trip with varint encoding for all components."""
        original_cigars = ["10M2I5D", "3S50M1D", "100M"]

        # Encode
        compressed = compress_string_cigar_decomposed(
            original_cigars,
            compress_integer_list_varint,  # num_ops encoder
            compress_integer_list_varint,  # lengths encoder
            lambda x: x,  # ops_string encoder (identity)
        )

        # Decode
        decompressed = decompress_string_cigar_decomposed(
            compressed,
            len(original_cigars),
            decode_integer_list_varint,  # num_ops decoder
            decode_integer_list_varint,  # lengths decoder
            lambda x: x,  # ops_string decoder (identity)
        )

        # Compare as bytes since decompress returns list[bytes]
        expected = [c.encode("ascii") for c in original_cigars]
        self.assertEqual(expected, decompressed)

    def test_roundtrip_with_gzip_ops(self):
        """Test round-trip where ops string is compressed with gzip."""
        original_cigars = ["10M", "20M"]  # Repeated patterns compress well with gzip

        import gzip

        # Encode
        compressed = compress_string_cigar_decomposed(
            original_cigars,
            compress_integer_list_varint,  # num_ops encoder
            compress_integer_list_varint,  # lengths encoder
            gzip.compress,  # ops_string encoder
        )

        # Decode
        decompressed = decompress_string_cigar_decomposed(
            compressed,
            len(original_cigars),
            decode_integer_list_varint,  # num_ops decoder
            decode_integer_list_varint,  # lengths decoder
            gzip.decompress,  # ops_string decoder
        )

        expected = [c.encode("ascii") for c in original_cigars]
        self.assertEqual(expected, decompressed)

    def test_roundtrip_star_alignment(self):
        """Test round-trip with '*' (no alignment) special case."""
        original_cigars = ["*"]  # Special case: single 0xFF byte in 2-byte encoding

        # Encode
        compressed = compress_string_cigar_decomposed(
            original_cigars,
            compress_integer_list_varint,  # num_ops encoder
            compress_integer_list_varint,  # lengths encoder
            lambda x: x,  # ops_string encoder (identity)
        )

        # Decode
        decompressed = decompress_string_cigar_decomposed(
            compressed,
            len(original_cigars),
            decode_integer_list_varint,  # num_ops decoder
            decode_integer_list_varint,  # lengths decoder
            lambda x: x,  # ops_string decoder (identity)
        )

        # For 4-byte decomposition, "*" encodes as zero operations -> empty string result
        # This represents the same semantic meaning (no alignment)
        expected = [b""]  # Zero operations encoded as empty string
        self.assertEqual(expected, decompressed)

    def test_empty_input(self):
        """Test that empty input produces empty output."""
        compressed = compress_string_cigar_decomposed(
            [],
            compress_integer_list_varint,
            compress_integer_list_varint,
            lambda x: x,
        )

        self.assertEqual(b"", compressed)

        decompressed = decompress_string_cigar_decomposed(
            compressed,
            0,
            decode_integer_list_varint,
            decode_integer_list_varint,
            lambda x: x,
        )

        self.assertEqual([], decompressed)


if __name__ == "__main__":
    unittest.main()
