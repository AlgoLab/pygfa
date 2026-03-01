#!/usr/bin/env python3

import os
import sys
import tempfile
import struct

sys.path.insert(0, '.')

from pygfa.gfa import GFA
from pygfa.bgfa import INTEGER_ENCODING_FIXED64, STRING_ENCODING_NONE, make_compression_code
from pygfa.bgfa import get_integer_decoder, decode_integer_list_fixed64

def test_fixed64_encoding():
    """Test fixed64 encoding specifically."""
    # Test the actual encoding/decoding of segment name lengths
    # Segment names are: ['0', '1', '10', '11', '12', '13', '14', '15', '18', '2', '23', '3', '4', '5', '6', '7', '8', '9']
    # Their lengths are: [1, 1, 2, 2, 2, 2, 2, 2, 2, 1, 2, 1, 1, 1, 1, 1, 1, 1]
    
    lengths = [1, 1, 2, 2, 2, 2, 2, 2, 2, 1, 2, 1, 1, 1, 1, 1, 1, 1]
    print(f"Segment name lengths: {lengths}")
    
    # Encode with fixed64
    encoded = b''
    for length in lengths:
        encoded += struct.pack('<Q', length)
    
    print(f"Encoded length: {len(encoded)} bytes")
    print(f"Encoded data (hex): {encoded.hex()}")
    
    # Decode
    decoded, consumed = decode_integer_list_fixed64(encoded, len(lengths))
    print(f"Decoded: {decoded}")
    print(f"Consumed: {consumed} bytes")
    print(f"Match original? {lengths == decoded}")
    
    # Now test with the actual encoder
    from pygfa.encoding.integer_list_encoding import compress_integer_list_fixed
    encoded2 = compress_integer_list_fixed(lengths, size=64)
    print(f"\nUsing compress_integer_list_fixed:")
    print(f"Encoded length: {len(encoded2)} bytes")
    print(f"Encoded data (hex): {encoded2.hex()}")
    
    decoded2, consumed2 = decode_integer_list_fixed64(encoded2, len(lengths))
    print(f"Decoded: {decoded2}")
    print(f"Consumed: {consumed2} bytes")
    print(f"Match original? {lengths == decoded2}")

if __name__ == "__main__":
    test_fixed64_encoding()
