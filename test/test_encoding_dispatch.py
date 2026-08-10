#!/usr/bin/env python3
"""Header-honesty tests: verify the dispatch layer maps each codec to its own
implementation, not a silent fallback.

See ``docs/encoding-review.md`` — the review found that 9 integer codecs and
``zstd_dict`` were silently falling back to varint/none in the reader/writer
dispatch, causing headers that claim one codec but payloads using another.
"""

import sys
import unittest

sys.path.insert(0, "..")

from pygfa.bgfa._reader import (
    INTEGER_DECODERS,
    STRING_DECODERS,
    get_integer_decoder_from_code,
    get_integer_encoder_from_code,
)
from pygfa.bgfa._constants import (
    INTEGER_ENCODING_NONE,
    INTEGER_ENCODING_VARINT,
    INTEGER_ENCODING_FIXED16,
    INTEGER_ENCODING_FIXED32,
    INTEGER_ENCODING_FIXED64,
    INTEGER_ENCODING_PFOR_DELTA,
    INTEGER_ENCODING_SIMPLE_8B,
    INTEGER_ENCODING_GROUP_VARINT,
    INTEGER_ENCODING_BIT_PACKING,
    INTEGER_ENCODING_FIBONACCI,
    INTEGER_ENCODING_EXP_GOLOMB,
    INTEGER_ENCODING_BYTE_PACKED,
    INTEGER_ENCODING_MASKED_VBYTE,
    INTEGER_ENCODING_GOLOMB,
    INTEGER_ENCODING_RICE,
    INTEGER_ENCODING_STREAMVBYTE,
    INTEGER_ENCODING_VBYTE,
    STRING_ENCODING_NONE,
    STRING_ENCODING_ZSTD,
    STRING_ENCODING_ZSTD_DICT,
    STRING_ENCODING_GZIP,
    STRING_ENCODING_LZMA,
    STRING_ENCODING_HUFFMAN,
    STRING_ENCODING_2BIT_DNA,
    STRING_ENCODING_ARITHMETIC,
    STRING_ENCODING_BWT_HUFFMAN,
    STRING_ENCODING_RLE,
    STRING_ENCODING_DICTIONARY,
    STRING_ENCODING_LZ4,
    STRING_ENCODING_BROTLI,
    STRING_ENCODING_PPM,
)
from pygfa.encoding import (
    compress_integer_list_none,
    compress_integer_list_varint,
    compress_integer_list_fixed,
    compress_integer_list_golomb,
    compress_integer_list_rice,
    compress_integer_list_streamvbyte,
    compress_integer_list_vbyte,
    compress_integer_list_pfor_delta,
    compress_integer_list_simple8b,
    compress_integer_list_group_varint,
    compress_integer_list_bitpacking,
    compress_integer_list_fibonacci,
    compress_integer_list_exp_golomb,
    compress_integer_list_byte_packed,
    compress_integer_list_masked_vbyte,
    compress_string_list,
)
from pygfa.encoding.integer_list_encoding import (
    decode_integer_list_none,
    decode_integer_list_varint,
    decode_integer_list_fixed16,
    decode_integer_list_fixed32,
    decode_integer_list_fixed64,
    decode_integer_list_golomb,
    decode_integer_list_rice,
    decode_integer_list_streamvbyte,
    decode_integer_list_vbyte,
)
from pygfa.encoding.pfor_delta import decompress_integer_list_pfor_delta
from pygfa.encoding.simple8b import decompress_integer_list_simple8b
from pygfa.encoding.group_varint import decompress_integer_list_group_varint
from pygfa.encoding.bit_packing import decompress_integer_list_bitpacking
from pygfa.encoding.fibonacci_coding import decompress_integer_list_fibonacci
from pygfa.encoding.exp_golomb import decompress_integer_list_exp_golomb
from pygfa.encoding.byte_packed import decompress_integer_list_byte_packed
from pygfa.encoding.masked_vbyte import decompress_integer_list_masked_vbyte
from pygfa.encoding.string_encoding import (
    decompress_string_none,
    decompress_string_zstd,
    decompress_string_gzip,
    decompress_string_lzma,
    decompress_string_lz4,
    decompress_string_brotli,
    decompress_string_huffman,
    decompress_string_zstd_dict_list,
)
from pygfa.encoding.dna_encoding import decompress_string_2bit_dna_strings
from pygfa.encoding.arithmetic_coding import (
    _decompress_string_arithmetic_wrapper,
    _decompress_string_bwt_huffman_wrapper,
)
from pygfa.encoding.rle_encoding import _decompress_string_rle_wrapper
from pygfa.encoding.dictionary_encoding import _decompress_string_dictionary_wrapper
from pygfa.encoding.ppm_coding import decompress_string_ppm_wrapper
from pygfa.encoding.integer_list_encoding import (
    compress_integer_list_varint as _varint_encoder,
    decode_integer_list_varint as _varint_decoder,
)
from pygfa.exceptions import InvalidEncodingError


# Integer test data (small values that all codecs can handle)
_INT_DATA = [1, 5, 3, 99, 2, 7, 11, 42, 5, 3, 8, 2, 1, 0, 4]

# All integer codec mappings: (code, own_encoder, own_decoder)
# elias_gamma/elias_omega are excluded: they are known-broken codecs
# (pre-existing, not a dispatch issue — per-section tests skip them too).
_INT_CODECS = [
    (INTEGER_ENCODING_NONE, compress_integer_list_none, decode_integer_list_none),
    (INTEGER_ENCODING_VARINT, compress_integer_list_varint, decode_integer_list_varint),
    (INTEGER_ENCODING_FIXED16, lambda x: compress_integer_list_fixed(x, 16), decode_integer_list_fixed16),
    (INTEGER_ENCODING_FIXED32, lambda x: compress_integer_list_fixed(x, 32), decode_integer_list_fixed32),
    (INTEGER_ENCODING_FIXED64, lambda x: compress_integer_list_fixed(x, 64), decode_integer_list_fixed64),
    (INTEGER_ENCODING_GOLOMB, compress_integer_list_golomb, decode_integer_list_golomb),
    (INTEGER_ENCODING_RICE, compress_integer_list_rice, decode_integer_list_rice),
    (INTEGER_ENCODING_STREAMVBYTE, compress_integer_list_streamvbyte, decode_integer_list_streamvbyte),
    (INTEGER_ENCODING_VBYTE, compress_integer_list_vbyte, decode_integer_list_vbyte),
    (INTEGER_ENCODING_PFOR_DELTA, compress_integer_list_pfor_delta, decompress_integer_list_pfor_delta),
    (INTEGER_ENCODING_SIMPLE_8B, compress_integer_list_simple8b, decompress_integer_list_simple8b),
    (INTEGER_ENCODING_GROUP_VARINT, compress_integer_list_group_varint, decompress_integer_list_group_varint),
    (INTEGER_ENCODING_BIT_PACKING, compress_integer_list_bitpacking, decompress_integer_list_bitpacking),
    (INTEGER_ENCODING_FIBONACCI, compress_integer_list_fibonacci, decompress_integer_list_fibonacci),
    (INTEGER_ENCODING_EXP_GOLOMB, compress_integer_list_exp_golomb, decompress_integer_list_exp_golomb),
    (INTEGER_ENCODING_BYTE_PACKED, compress_integer_list_byte_packed, decompress_integer_list_byte_packed),
    (INTEGER_ENCODING_MASKED_VBYTE, compress_integer_list_masked_vbyte, decompress_integer_list_masked_vbyte),
]

# ACGTN-only so the 2-bit DNA codec works. rle/dictionary are known-broken
# on short/unique strings (per-section tests skip them too), so excluded.
_STRING_DATA = ["ACGT", "NNN", "AAAA", "CGTACG", "TTTTT"]
_SKIP_STR_METHODS = {"rle", "dictionary"}

# String codec mappings: (code, method_name, own_decoder)
_STR_CODECS = [
    (STRING_ENCODING_NONE, "none", decompress_string_none),
    (STRING_ENCODING_ZSTD, "zstd", decompress_string_zstd),
    (STRING_ENCODING_ZSTD_DICT, "zstd_dict", decompress_string_zstd_dict_list),
    (STRING_ENCODING_GZIP, "gzip", decompress_string_gzip),
    (STRING_ENCODING_LZMA, "lzma", decompress_string_lzma),
    (STRING_ENCODING_LZ4, "lz4", decompress_string_lz4),
    (STRING_ENCODING_BROTLI, "brotli", decompress_string_brotli),
    (STRING_ENCODING_HUFFMAN, "huffman", decompress_string_huffman),
    (STRING_ENCODING_2BIT_DNA, "2bit", decompress_string_2bit_dna_strings),
    (STRING_ENCODING_ARITHMETIC, "arithmetic", _decompress_string_arithmetic_wrapper),
    (STRING_ENCODING_BWT_HUFFMAN, "bwt_huffman", _decompress_string_bwt_huffman_wrapper),
    (STRING_ENCODING_RLE, "rle", _decompress_string_rle_wrapper),
    (STRING_ENCODING_DICTIONARY, "dictionary", _decompress_string_dictionary_wrapper),
    (STRING_ENCODING_PPM, "ppm", decompress_string_ppm_wrapper),
]


class TestIntegerDispatchHonesty(unittest.TestCase):
    """Verify the integer dispatch maps each codec to its own implementation."""

    def test_encode_own_decode_dispatch(self):
        """Encode with codec's own compressor, decode through dispatch."""
        for code, own_enc, _ in _INT_CODECS:
            with self.subTest(code=code):
                payload = own_enc(_INT_DATA)
                decoder = get_integer_decoder_from_code(code)
                out, consumed = decoder(payload, len(_INT_DATA))
                self.assertEqual(list(out), _INT_DATA,
                    f"Dispatch decoder for code {code:#x} did not produce correct data")

    def test_encode_dispatch_decode_own(self):
        """Encode through dispatch, decode with codec's own decompressor."""
        for code, _, own_dec in _INT_CODECS:
            with self.subTest(code=code):
                encoder = get_integer_encoder_from_code(code)
                payload = encoder(_INT_DATA)
                out, consumed = own_dec(payload, len(_INT_DATA))
                self.assertEqual(list(out), _INT_DATA,
                    f"Dispatch encoder for code {code:#x} did not produce correct data")

    def test_unknown_code_raises(self):
        """Unknown integer codes raise InvalidEncodingError, not silent fallback."""
        for fn in [get_integer_decoder_from_code, get_integer_encoder_from_code]:
            with self.subTest(fn=fn.__name__):
                with self.assertRaises(InvalidEncodingError):
                    fn(0xFF)
                with self.assertRaises(InvalidEncodingError):
                    fn(0xFE)

    def test_all_codes_in_dispatch_dict(self):
        """Every code in _INT_CODECS appears in INTEGER_DECODERS."""
        for code, _, _ in _INT_CODECS:
            self.assertIn(code, INTEGER_DECODERS,
                f"Code {code:#x} missing from INTEGER_DECODERS")


class TestStringDispatchHonesty(unittest.TestCase):
    """Verify the string dispatch maps each codec to its own implementation."""

    def test_decode_via_dispatch(self):
        """Compress with own method, decompress through dispatch."""
        for code, method, _ in _STR_CODECS:
            if method in _SKIP_STR_METHODS:
                continue
            with self.subTest(code=code, method=method):
                payload = compress_string_list(_STRING_DATA, _varint_encoder, method)
                decoder = STRING_DECODERS.get(code)
                self.assertIsNotNone(decoder,
                    f"Code {code:#x} ({method}) missing from STRING_DECODERS")
                result = decoder(payload, len(_STRING_DATA), _varint_decoder)
                expected = [s.encode("ascii") for s in _STRING_DATA]
                self.assertEqual(result, expected,
                    f"Dispatch decoder for {method} (code {code:#x}) produced wrong data")

    def test_own_decoder_in_dispatch(self):
        """Verify the dispatch function is the codec's own, not a fallback."""
        for code, method, own_dec in _STR_CODECS:
            if method in _SKIP_STR_METHODS:
                continue
            with self.subTest(code=code, method=method):
                dispatch_dec = STRING_DECODERS.get(code)
                self.assertIsNotNone(dispatch_dec,
                    f"Code {code:#x} ({method}) missing from STRING_DECODERS")
                # For non-wrapper codecs, verify exact match.
                # PPM, RLE, dictionary use wrapper functions in STRING_DECODERS.
                if method not in {"ppm", "rle", "dictionary"}:
                    self.assertIs(dispatch_dec, own_dec,
                        f"STRING_DECODERS for {method} (code {code:#x}) is "
                        f"{dispatch_dec}, expected own decoder {own_dec}")


if __name__ == "__main__":
    unittest.main()