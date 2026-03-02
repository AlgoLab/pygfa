#!/usr/bin/env python3

import os
import sys
import struct

sys.path.insert(0, '.')

from pygfa.bgfa import get_integer_decoder, decode_integer_list_fixed64
from pygfa.encoding.integer_list_encoding import compress_integer_list_fixed

def test_fixed64_edge_case():
    """Test a specific edge case that might be causing the issue."""
    
    # Let's test what happens with the actual segment IDs that would be written
    # Based on the GFA file, we have segments like '0', '1', '2', '3', etc.
    # These get mapped to indices in segment_map
    
    # Segment names in the order they appear in the file:
    # ['1', '2', '3', '4', '5', '6', '8', '23', '10', '11', '14', '15', '9', '18', '0', '7', '12', '13']
    # Actually from the file: S lines are in order: 1,2,3,4,5,6,8,23,10,11,14,15,9,18,0,7,12,13
    
    segment_names = ['1', '2', '3', '4', '5', '6', '8', '23', '10', '11', '14', '15', '9', '18', '0', '7', '12', '13']
    segment_map = {name: idx for idx, name in enumerate(segment_names)}
    
    print("Segment mapping (0-based):")
    for name in sorted(segment_names):
        print(f"  '{name}' -> {segment_map[name]}")
    
    print("\nSegment mapping (1-based as stored):")
    for name in sorted(segment_names):
        print(f"  '{name}' -> {segment_map[name] + 1}")
    
    # Now let's look at the first link: L 1 + 2 + 5M
    # from_name = '1', to_name = '2'
    from_name = '1'
    to_name = '2'
    
    from_id = segment_map.get(from_name, -1) + 1
    to_id = segment_map.get(to_name, -1) + 1
    
    print(f"\nLink '1 + 2':")
    print(f"  from_name='{from_name}' -> index {segment_map[from_name]} -> stored as {from_id}")
    print(f"  to_name='{to_name}' -> index {segment_map[to_name]} -> stored as {to_id}")
    
    # Test encoding/decoding of these IDs
    test_ids = [from_id, to_id]
    print(f"\nTest IDs to encode: {test_ids}")
    
    # Encode with fixed64
    encoded = compress_integer_list_fixed(test_ids, size=64)
    print(f"Encoded ({len(encoded)} bytes): {encoded.hex()}")
    
    # Decode
    decoded, consumed = decode_integer_list_fixed64(encoded, len(test_ids))
    print(f"Decoded: {decoded}, consumed: {consumed}")
    
    # Now test with a problematic case: what about segment '0'?
    from_name = '0'
    to_name = '12'
    
    from_id = segment_map.get(from_name, -1) + 1
    to_id = segment_map.get(to_name, -1) + 1
    
    print(f"\nLink '0 - 12':")
    print(f"  from_name='{from_name}' -> index {segment_map[from_name]} -> stored as {from_id}")
    print(f"  to_name='{to_name}' -> index {segment_map[to_name]} -> stored as {to_id}")
    
    test_ids2 = [from_id, to_id]
    print(f"Test IDs to encode: {test_ids2}")
    
    encoded2 = compress_integer_list_fixed(test_ids2, size=64)
    print(f"Encoded ({len(encoded2)} bytes): {encoded2.hex()}")
    
    decoded2, consumed2 = decode_integer_list_fixed64(encoded2, len(test_ids2))
    print(f"Decoded: {decoded2}, consumed: {consumed2}")

if __name__ == "__main__":
    test_fixed64_edge_case()
