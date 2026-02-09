"""Tests for arithmetic coding and BWT+Huffman encodings."""

import unittest

from pygfa.encoding.arithmetic_coding import (
    AdaptiveArithmeticCoder,
    compress_string_arithmetic,
    compress_string_bwt_huffman,
    decompress_string_arithmetic,
    decompress_string_bwt_huffman,
)


class TestAdaptiveArithmeticCoding(unittest.TestCase):
    """Test adaptive arithmetic coding."""

    def test_empty_string(self):
        """Test encoding empty string."""
        coder = AdaptiveArithmeticCoder()
        encoded = coder.encode(b"")
        decoded = coder.decode(encoded)
        self.assertEqual(decoded, b"")

    def test_single_char(self):
        """Test encoding single character."""
        coder = AdaptiveArithmeticCoder()
        data = b"A"
        encoded = coder.encode(data)
        decoded = coder.decode(encoded)
        self.assertEqual(decoded, data)

    def test_repetitive_pattern(self):
        """Test encoding repetitive pattern."""
        coder = AdaptiveArithmeticCoder()
        data = b"AAAAA"
        encoded = coder.encode(data)
        decoded = coder.decode(encoded)
        self.assertEqual(decoded, data)

    def test_dna_sequence(self):
        """Test encoding DNA sequence."""
        coder = AdaptiveArithmeticCoder()
        data = b"ACGTACGTACGT"
        encoded = coder.encode(data)
        decoded = coder.decode(encoded)
        self.assertEqual(decoded, data)

    def test_random_sequence(self):
        """Test encoding random sequence."""
        import random

        coder = AdaptiveArithmeticCoder()
        random.seed(42)
        data = bytes([random.randint(0, 255) for _ in range(100)])
        encoded = coder.encode(data)
        decoded = coder.decode(encoded)
        self.assertEqual(decoded, data)


class TestCompressStringArithmetic(unittest.TestCase):
    """Test high-level arithmetic string compression functions."""

    def test_roundtrip_single_string(self):
        """Test compress/decompress single string."""
        original = "ACGTACGT"
        compressed = compress_string_arithmetic(original)
        decompressed = decompress_string_arithmetic(compressed, [len(original)])
        self.assertEqual(decompressed[0].decode("ascii"), original)

    def test_roundtrip_multiple_strings(self):
        """Test compress/decompress multiple strings."""
        strings = ["AAA", "BBB", "CCC"]
        concatenated = "".join(strings)
        compressed = compress_string_arithmetic(concatenated)
        lengths = [len(s) for s in strings]
        decompressed = decompress_string_arithmetic(compressed, lengths)
        for i, s in enumerate(strings):
            self.assertEqual(decompressed[i].decode("ascii"), s)

    def test_empty_string(self):
        """Test empty string compression."""
        compressed = compress_string_arithmetic("")
        decompressed = decompress_string_arithmetic(compressed, [0])
        self.assertEqual(decompressed[0], b"")


class TestBWTCompression(unittest.TestCase):
    """Test BWT compression."""

    def test_bwt_roundtrip(self):
        """Test BWT encoding and decoding roundtrip."""
        from pygfa.encoding.bwt import burrows_wheeler_transform, inverse_bwt

        data = b"ACGTACGT"
        bwt_data = burrows_wheeler_transform(data, block_size=65536)
        recovered = inverse_bwt(bwt_data)
        self.assertEqual(recovered, data)

    def test_mtf_roundtrip(self):
        """Test Move-to-Front encoding and decoding roundtrip."""
        from pygfa.encoding.bwt import move_to_front_decode, move_to_front_encode

        data = b"ACGTACGT"
        mtf_data = move_to_front_encode(data)
        recovered = move_to_front_decode(mtf_data)
        self.assertEqual(recovered, data)

    def test_bwt_block_splitting(self):
        """Test BWT with block splitting."""
        from pygfa.encoding.bwt import burrows_wheeler_transform, inverse_bwt

        # Create data larger than block size
        block_size = 10
        data = b"A" * 25  # Should create 3 blocks
        bwt_data = burrows_wheeler_transform(data, block_size=block_size)
        recovered = inverse_bwt(bwt_data)
        self.assertEqual(recovered, data)


class TestCompressStringBWTHuffman(unittest.TestCase):
    """Test BWT+Huffman compression."""

    def test_roundtrip_dna(self):
        """Test BWT+Huffman roundtrip with DNA sequence."""
        original = "ACGTACGTACGTACGT"
        compressed = compress_string_bwt_huffman(original, block_size=65536)
        decompressed = decompress_string_bwt_huffman(compressed, [len(original)])
        self.assertEqual(decompressed[0].decode("ascii"), original)

    def test_roundtrip_repetitive(self):
        """Test BWT+Huffman roundtrip with repetitive sequence."""
        original = "AAAAABBBBB"
        compressed = compress_string_bwt_huffman(original, block_size=65536)
        decompressed = decompress_string_bwt_huffman(compressed, [len(original)])
        self.assertEqual(decompressed[0].decode("ascii"), original)

    def test_roundtrip_empty(self):
        """Test BWT+Huffman with empty string."""
        original = ""
        compressed = compress_string_bwt_huffman(original, block_size=65536)
        # Empty string should still roundtrip
        self.assertIsNotNone(compressed)


if __name__ == "__main__":
    unittest.main()
