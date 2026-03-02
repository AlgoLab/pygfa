#!/usr/bin/env python3

import os
import sys
import struct

sys.path.insert(0, '.')

from pygfa.bgfa import decode_integer_list_fixed64

def test_edge_case():
    """Test edge case in decode_integer_list_fixed64."""
    
    # Test what happens with count parameter
    test_data = struct.pack('<Q', 1) + struct.pack('<Q', 2) + struct.pack('<Q', 3)
    
    # Test 1: count = 3
    result1, consumed1 = decode_integer_list_fixed64(test_data, 3)
    print(f"Test 1 (count=3): {result1}, consumed={consumed1}")
    
    # Test 2: count = 2  
    result2, consumed2 = decode_integer_list_fixed64(test_data, 2)
    print(f"Test 2 (count=2): {result2}, consumed={consumed2}")
    
    # Test 3: count = 4 (more than available)
    result3, consumed3 = decode_integer_list_fixed64(test_data, 4)
    print(f"Test 3 (count=4): {result3}, consumed={consumed3}")
    
    # Test 4: count = -1 (all available)
    result4, consumed4 = decode_integer_list_fixed64(test_data, -1)
    print(f"Test 4 (count=-1): {result4}, consumed={consumed4}")
    
    # Test with partial data
    partial_data = struct.pack('<Q', 1) + struct.pack('<Q', 2)  # Only 16 bytes
    result5, consumed5 = decode_integer_list_fixed64(partial_data, 3)
    print(f"Test 5 (partial data, count=3): {result5}, consumed={consumed5}")

if __name__ == "__main__":
    test_edge_case()
