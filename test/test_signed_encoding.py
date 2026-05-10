import unittest
import sys

sys.path.insert(0, "../")

from pygfa.encoding.integer_list_encoding import compress_integer_list_varint, decode_integer_list_varint
from pygfa.encoding.signed_encoding import compress_signed_integers, decode_signed_integers


class TestSignedEncoding(unittest.TestCase):
    """Test signed integer encoding (sign bits RLE + abs values)."""

    def test_all_positive(self):
        data = [5, 10, 15]
        encoded = compress_signed_integers(data, compress_integer_list_varint)
        decoded, consumed = decode_signed_integers(encoded, len(data), decode_integer_list_varint)
        self.assertEqual(decoded, data)
        self.assertEqual(consumed, len(encoded))

    def test_all_negative(self):
        data = [-5, -10, -15]
        encoded = compress_signed_integers(data, compress_integer_list_varint)
        decoded, consumed = decode_signed_integers(encoded, len(data), decode_integer_list_varint)
        self.assertEqual(decoded, data)

    def test_mixed_signs(self):
        data = [0, -1, 2, -3, 4, -5]
        encoded = compress_signed_integers(data, compress_integer_list_varint)
        decoded, consumed = decode_signed_integers(encoded, len(data), decode_integer_list_varint)
        self.assertEqual(decoded, data)

    def test_with_zero(self):
        data = [0, 0, 0, 0]
        encoded = compress_signed_integers(data, compress_integer_list_varint)
        decoded, consumed = decode_signed_integers(encoded, len(data), decode_integer_list_varint)
        self.assertEqual(decoded, data)

    def test_all_positive_starts_with_zero(self):
        data = [0, 5, 10]
        encoded = compress_signed_integers(data, compress_integer_list_varint)
        decoded, consumed = decode_signed_integers(encoded, len(data), decode_integer_list_varint)
        self.assertEqual(decoded, data)

    def test_alternating_signs(self):
        data = [1, -1, 1, -1, 1, -1]
        encoded = compress_signed_integers(data, compress_integer_list_varint)
        decoded, consumed = decode_signed_integers(encoded, len(data), decode_integer_list_varint)
        self.assertEqual(decoded, data)

    def test_single_positive(self):
        data = [42]
        encoded = compress_signed_integers(data, compress_integer_list_varint)
        decoded, consumed = decode_signed_integers(encoded, len(data), decode_integer_list_varint)
        self.assertEqual(decoded, data)

    def test_single_negative(self):
        data = [-42]
        encoded = compress_signed_integers(data, compress_integer_list_varint)
        decoded, consumed = decode_signed_integers(encoded, len(data), decode_integer_list_varint)
        self.assertEqual(decoded, data)

    def test_empty_list(self):
        encoded = compress_signed_integers([], compress_integer_list_varint)
        self.assertEqual(encoded, b"")
        decoded, consumed = decode_signed_integers(encoded, 0, decode_integer_list_varint)
        self.assertEqual(decoded, [])

    def test_roundtrip_with_fixed32(self):
        from pygfa.encoding.integer_list_encoding import compress_integer_list_fixed, decode_integer_list_fixed32

        def _fixed32_encoder(values):
            return compress_integer_list_fixed(values, 32)

        data = [100, -200, 300, -400]
        encoded = compress_signed_integers(data, _fixed32_encoder)
        decoded, consumed = decode_signed_integers(encoded, len(data), decode_integer_list_fixed32)
        self.assertEqual(decoded, data)

    def test_first_bit_is_one(self):
        data = [-1, 2, 3]
        encoded = compress_signed_integers(data, compress_integer_list_varint)
        decoded, consumed = decode_signed_integers(encoded, len(data), decode_integer_list_varint)
        self.assertEqual(decoded, data)

    def test_all_ones_then_all_zeros(self):
        data = [-1, -2, -3, 4, 5, 6]
        encoded = compress_signed_integers(data, compress_integer_list_varint)
        decoded, consumed = decode_signed_integers(encoded, len(data), decode_integer_list_varint)
        self.assertEqual(decoded, data)


if __name__ == "__main__":
    unittest.main()
