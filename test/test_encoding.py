import unittest
import sys
import pytest

sys.path.insert(0, "../")

from pygfa.encoding.integer_list_encoding import (
    compress_integer_list_varint,
    compress_integer_list_fixed,
    compress_integer_list_none,
    compress_integer_list_delta,
    compress_integer_list_elias_gamma,
    compress_integer_list_elias_omega,
    compress_integer_list_golomb,
    compress_integer_list_rice,
    compress_integer_list_streamvbyte,
    compress_integer_list_vbyte,
)
from pygfa.encoding.string_encoding import (
    compress_string_zstd,
    compress_string_gzip,
    compress_string_lzma,
    compress_string_none,
    compress_string_list,
    compress_string_list_frontcoding,
    compress_string_list_delta,
    compress_string_list_dictionary,
    compress_string_list_huffman,
)


class TestIntegerListEncoding(unittest.TestCase):
    """Test integer list compression algorithms."""

    def test_compress_integer_list_varint(self):
        """Test variable byte integer encoding."""
        # Test with small numbers
        result = compress_integer_list_varint([1, 2, 3, 4])
        self.assertIsInstance(result, bytes)
        self.assertGreater(len(result), 0)

        # Test with large numbers
        result = compress_integer_list_varint([127, 128, 255, 256])
        self.assertIsInstance(result, bytes)

        # Test with empty list
        result = compress_integer_list_varint([])
        self.assertEqual(result, b"")

        # Test with single number
        result = compress_integer_list_varint([42])
        self.assertIsInstance(result, bytes)

    def test_compress_integer_list_fixed(self):
        """Test fixed-width integer encoding."""
        # Test with 32-bit integers
        result = compress_integer_list_fixed([1, 2, 3, 4], size=32)
        self.assertIsInstance(result, bytes)
        self.assertEqual(len(result), 4 * 4)  # 4 numbers * 4 bytes each

        # Test with invalid size
        with self.assertRaises(ValueError):
            compress_integer_list_fixed([1, 2, 3], size=7)

        with self.assertRaises(ValueError):
            compress_integer_list_fixed([1, 2, 3], size=33)

    def test_compress_integer_list_none(self):
        """Test no compression (comma-separated) encoding."""
        result = compress_integer_list_none([1, 2, 3, 4])
        self.assertEqual(result, b"1,2,3,4")

        result = compress_integer_list_none([])
        self.assertEqual(result, b"")

    @pytest.mark.limit_memory(10 * 1024 * 1024)  # 10 MB limit
    def test_compress_integer_list_delta(self):
        """Test delta encoding."""
        import time

        start_time = time.time()
        timeout = 5.0  # 5 seconds

        # Test sequential numbers
        result = compress_integer_list_delta([10, 20, 30, 40])
        self.assertIsInstance(result, bytes)

        # Test empty list
        result = compress_integer_list_delta([])
        self.assertEqual(result, b"")

        # Test single number
        result = compress_integer_list_delta([42])
        self.assertIsInstance(result, bytes)

        elapsed = time.time() - start_time
        self.assertLess(elapsed, timeout, f"Test took {elapsed:.2f}s, exceeded {timeout}s threshold")

    def test_compress_integer_list_elias_gamma(self):
        """Test Elias gamma encoding."""
        result = compress_integer_list_elias_gamma([1, 2, 3, 4])
        self.assertIsInstance(result, bytes)
        self.assertGreater(len(result), 0)

        # Test with zero
        result = compress_integer_list_elias_gamma([0, 1, 2])
        self.assertIsInstance(result, bytes)

    def test_compress_integer_list_elias_omega(self):
        """Test Elias omega encoding."""
        result = compress_integer_list_elias_omega([1, 2, 3, 4])
        self.assertIsInstance(result, bytes)

        # Test with zero
        result = compress_integer_list_elias_omega([0, 1, 2])
        self.assertIsInstance(result, bytes)

    def test_compress_integer_list_golomb(self):
        """Test Golomb coding."""
        result = compress_integer_list_golomb([1, 2, 3, 4, 5])
        self.assertIsInstance(result, bytes)
        self.assertGreater(len(result), 1)  # Should include divisor byte

        # Test empty list
        result = compress_integer_list_golomb([])
        self.assertEqual(result, b"")

    def test_compress_integer_list_rice(self):
        """Test Rice coding."""
        result = compress_integer_list_rice([1, 2, 3, 4, 5])
        self.assertIsInstance(result, bytes)
        self.assertGreater(len(result), 1)  # Should include parameter byte

    def test_compress_integer_list_streamvbyte(self):
        """Test StreamVByte encoding."""
        result = compress_integer_list_streamvbyte([1, 2, 3, 4])
        self.assertIsInstance(result, bytes)

        # Test empty list
        result = compress_integer_list_streamvbyte([])
        self.assertEqual(result, b"")

        # Test single value
        result = compress_integer_list_streamvbyte([42])
        self.assertIsInstance(result, bytes)

    def test_compress_integer_list_vbyte(self):
        """Test Variable Byte encoding."""
        result = compress_integer_list_vbyte([1, 2, 3, 4])
        self.assertIsInstance(result, bytes)

        # Test with larger values
        result = compress_integer_list_vbyte([100, 1000, 10000])
        self.assertIsInstance(result, bytes)


class TestStringEncoding(unittest.TestCase):
    """Test string compression algorithms."""

    def test_compress_string_gzip(self):
        """Test gzip compression."""
        result = compress_string_gzip("Hello, World!")
        self.assertIsInstance(result, bytes)
        self.assertGreater(len(result), 0)

        # Test with empty string
        result = compress_string_gzip("")
        self.assertIsInstance(result, bytes)

    def test_compress_string_lzma(self):
        """Test lzma compression."""
        result = compress_string_lzma("Hello, World!")
        self.assertIsInstance(result, bytes)
        self.assertGreater(len(result), 0)

    def test_compress_string_none(self):
        """Test no compression."""
        result = compress_string_none("Hello, World!")
        self.assertEqual(result, b"Hello, World!")

        result = compress_string_none("")
        self.assertEqual(result, b"")

    def test_compress_string_list(self):
        """Test string list compression with default method."""
        strings = ["hello", "world", "test"]
        result = compress_string_list(strings)
        self.assertIsInstance(result, bytes)
        self.assertGreater(len(result), 0)

        # Test empty list - zstd compression of empty data still produces metadata
        result = compress_string_list([])
        self.assertIsInstance(result, bytes)

    def test_compress_string_list_frontcoding(self):
        """Test front coding compression."""
        strings = ["hello", "help", "helicopter"]
        result = compress_string_list_frontcoding(strings)
        self.assertIsInstance(result, bytes)

        # Test empty list
        result = compress_string_list_frontcoding([])
        self.assertEqual(result, b"")

    def test_compress_string_list_delta(self):
        """Test delta encoding for strings."""
        strings = ["abc", "abd", "abf"]
        result = compress_string_list_delta(strings)
        self.assertIsInstance(result, bytes)

        # Test empty list
        result = compress_string_list_delta([])
        self.assertEqual(result, b"")

    def test_compress_string_list_dictionary(self):
        """Test dictionary compression."""
        strings = ["hello", "world", "hello", "test", "world"]
        result = compress_string_list_dictionary(strings)
        self.assertIsInstance(result, bytes)

        # Test empty list
        result = compress_string_list_dictionary([])
        self.assertEqual(result, b"")

    def test_compress_string_list_huffman(self):
        """Test Huffman coding."""
        strings = ["hello", "world", "hello", "test"]
        result = compress_string_list_huffman(strings)
        self.assertIsInstance(result, bytes)

        # Test empty list - returns empty bytes
        result = compress_string_list_huffman([])
        self.assertEqual(result, b"")

    def test_compress_string_zstd(self):
        """Test zstd compression - should raise ImportError if not available."""
        try:
            result = compress_string_zstd("Hello, World!")
            self.assertIsInstance(result, bytes)
        except ImportError:
            # Expected if zstd package is not available
            self.skipTest("zstd compression not available")


class TestEncodingEdgeCases(unittest.TestCase):
    """Test edge cases and error handling for encoding algorithms."""

    def test_various_input_types(self):
        """Test encoding algorithms with various input types."""
        # Test with generator input
        result = compress_integer_list_varint(i for i in range(5))
        self.assertIsInstance(result, bytes)

        # Test with tuple input
        result = compress_integer_list_varint((1, 2, 3, 4, 5))
        self.assertIsInstance(result, bytes)

    def test_unicode_strings(self):
        """Test string encoding with unicode characters."""
        # GFA files are ASCII-based, so unicode should raise an error
        with self.assertRaises(UnicodeEncodeError):
            compress_string_gzip("Hello, 世界!")

    def test_large_inputs(self):
        """Test encoding with large inputs."""
        large_list = list(range(1000))
        result = compress_integer_list_varint(large_list)
        self.assertIsInstance(result, bytes)
        self.assertGreater(len(result), 0)

        large_string = "a" * 10000
        result = compress_string_gzip(large_string)
        self.assertIsInstance(result, bytes)


if __name__ == "__main__":
    unittest.main()
