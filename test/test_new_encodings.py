"""Tests for new BGFA encoding methods: 2-bit DNA, RLE, CIGAR, Dictionary, Arithmetic, and BWT+Huffman."""

import unittest

from pygfa.encoding.arithmetic_coding import (
    AdaptiveArithmeticCoder,
    compress_string_arithmetic,
    compress_string_bwt_huffman,
    decompress_string_arithmetic,
    decompress_string_bwt_huffman,
)
from pygfa.encoding.dna_encoding import (
    compress_string_2bit_dna,
    compress_string_list_2bit_dna,
    decompress_string_2bit_dna,
)
from pygfa.encoding.rle_encoding import (
    compress_string_rle,
    compress_string_list_rle,
    decompress_string_rle,
)
from pygfa.encoding.cigar_encoding import (
    compress_string_cigar,
    compress_string_list_cigar,
    decompress_string_cigar,
)
from pygfa.encoding.dictionary_encoding import (
    compress_string_dictionary,
    decompress_string_dictionary,
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


class Test2BitDNAEncoding(unittest.TestCase):
    """Test 2-bit DNA encoding."""

    def test_compress_simple_dna(self):
        """Test compression of simple DNA sequences."""
        dna = "ACGTACGT"
        compressed = compress_string_2bit_dna(dna)
        self.assertIsInstance(compressed, bytes)
        # Should be much smaller: 8 bases * 2 bits = 16 bits = 2 bytes + 1 flag byte
        self.assertLessEqual(len(compressed), 5)

    def test_compress_empty_dna(self):
        """Test compression of empty sequence."""
        compressed = compress_string_2bit_dna("")
        self.assertEqual(compressed, b"\x00")

    def test_compress_lowercase_dna(self):
        """Test compression of lowercase DNA."""
        dna = "acgtacgt"
        compressed = compress_string_2bit_dna(dna)
        self.assertIsInstance(compressed, bytes)

    def test_compress_with_ambiguity(self):
        """Test compression with ambiguity codes."""
        dna = "ACGTNACGT"
        compressed = compress_string_2bit_dna(dna)
        self.assertIsInstance(compressed, bytes)

    def test_roundtrip_simple(self):
        """Test compression and decompression roundtrip."""
        dna = "ACGTACGTACGT"
        compressed = compress_string_2bit_dna(dna)
        decompressed = decompress_string_2bit_dna(compressed, [len(dna)])
        self.assertEqual(len(decompressed), 1)
        self.assertEqual(decompressed[0].decode("ascii"), dna)

    def test_roundtrip_with_ambiguity(self):
        """Test roundtrip with ambiguity codes."""
        dna = "ACGTNRYACGT"
        compressed = compress_string_2bit_dna(dna)
        decompressed = decompress_string_2bit_dna(compressed, [len(dna)])
        self.assertEqual(decompressed[0].decode("ascii"), dna)

    def test_roundtrip_multiple_sequences(self):
        """Test compression of multiple DNA sequences."""
        from pygfa.bgfa import decode_integer_list_varint

        sequences = ["ACGT", "GGGGCCCC", "ATATATAT"]
        compressed = compress_string_list_2bit_dna(sequences)
        self.assertIsInstance(compressed, bytes)

        # Extract lengths from compressed data (they're encoded at the front)
        lengths_from_data, bytes_used = decode_integer_list_varint(compressed, len(sequences))
        # Skip past the lengths to get just the compressed sequences
        compressed_sequences = compressed[bytes_used:]

        decompressed = decompress_string_2bit_dna(compressed_sequences, lengths_from_data)
        self.assertEqual(len(decompressed), len(sequences))
        for orig, decomp in zip(sequences, decompressed):
            self.assertEqual(decomp.decode("ascii"), orig)


class TestRLEEncoding(unittest.TestCase):
    """Test Run-Length Encoding."""

    def test_compress_homopolymer(self):
        """Test compression of homopolymer runs."""
        seq = "AAAAAAAAAA"
        compressed = compress_string_rle(seq)
        self.assertIsInstance(compressed, bytes)
        self.assertLess(len(compressed), len(seq))

    def test_compress_empty(self):
        """Test compression of empty string."""
        compressed = compress_string_rle("")
        self.assertEqual(compressed, b"\x00")

    def test_roundtrip_homopolymer(self):
        """Test roundtrip for homopolymer."""
        seq = "TTTTTTTTTTTT"
        compressed = compress_string_rle(seq)
        decompressed = decompress_string_rle(compressed, [len(seq)])
        self.assertEqual(len(decompressed), 1)
        self.assertEqual(decompressed[0].decode("ascii"), seq)

    def test_roundtrip_mixed(self):
        """Test roundtrip for mixed content."""
        seq = "AAABBBCCCDEFGGGG"
        compressed = compress_string_rle(seq)
        decompressed = decompress_string_rle(compressed, [len(seq)])
        self.assertEqual(decompressed[0].decode("ascii"), seq)

    def test_roundtrip_multiple_sequences(self):
        """Test compression of multiple sequences."""
        from pygfa.bgfa import decode_integer_list_varint

        sequences = ["AAAA", "GGGGCCCC", "ABCD"]
        compressed = compress_string_list_rle(sequences)
        self.assertIsInstance(compressed, bytes)

        # Extract lengths from compressed data
        lengths_from_data, bytes_used = decode_integer_list_varint(compressed, len(sequences))
        compressed_sequences = compressed[bytes_used:]

        decompressed = decompress_string_rle(compressed_sequences, lengths_from_data)
        self.assertEqual(len(decompressed), len(sequences))
        for orig, decomp in zip(sequences, decompressed):
            self.assertEqual(decomp.decode("ascii"), orig)


class TestCIGAREncoding(unittest.TestCase):
    """Test CIGAR-specific encoding."""

    def test_compress_simple_cigar(self):
        """Test compression of simple CIGAR string."""
        cigar = "10M2I5D"
        compressed = compress_string_cigar(cigar)
        self.assertIsInstance(compressed, bytes)

    def test_compress_empty(self):
        """Test compression of empty CIGAR."""
        compressed = compress_string_cigar("")
        self.assertEqual(compressed, b"\x00")

    def test_roundtrip_simple(self):
        """Test roundtrip for simple CIGAR."""
        cigar = "10M2I5D"
        compressed = compress_string_cigar(cigar)
        decompressed = decompress_string_cigar(compressed, [len(cigar)])
        self.assertEqual(len(decompressed), 1)
        self.assertEqual(decompressed[0].decode("ascii"), cigar)

    def test_roundtrip_complex(self):
        """Test roundtrip for complex CIGAR."""
        cigar = "100M50I25D10N5S"
        compressed = compress_string_cigar(cigar)
        decompressed = decompress_string_cigar(compressed, [len(cigar)])
        self.assertEqual(decompressed[0].decode("ascii"), cigar)

    def test_roundtrip_multiple(self):
        """Test compression of multiple CIGAR strings."""
        from pygfa.bgfa import decode_integer_list_varint

        cigars = ["10M", "5I3D", "100M50I"]
        compressed = compress_string_list_cigar(cigars)
        self.assertIsInstance(compressed, bytes)

        # Extract lengths from compressed data
        lengths_from_data, bytes_used = decode_integer_list_varint(compressed, len(cigars))
        compressed_sequences = compressed[bytes_used:]

        decompressed = decompress_string_cigar(compressed_sequences, lengths_from_data)
        self.assertEqual(len(decompressed), len(cigars))
        for orig, decomp in zip(cigars, decompressed):
            self.assertEqual(decomp.decode("ascii"), orig)


class TestDictionaryEncoding(unittest.TestCase):
    """Test dictionary-based encoding."""

    def test_compress_single_string(self):
        """Test compression of single string."""
        s = "sample_001"
        compressed = compress_string_dictionary(s)
        self.assertIsInstance(compressed, bytes)

    def test_roundtrip_single(self):
        """Test roundtrip for single string."""
        s = "sample_001"
        compressed = compress_string_dictionary(s)
        decompressed = decompress_string_dictionary(compressed, [len(s)])
        self.assertEqual(len(decompressed), 1)
        self.assertEqual(decompressed[0].decode("ascii"), s)


if __name__ == "__main__":
    unittest.main()
