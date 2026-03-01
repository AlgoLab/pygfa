#!/usr/bin/env python3
import struct

# Test fixed64 encoding/decoding
def encode_fixed64(values):
    result = b''
    for val in values:
        result += struct.pack('<Q', val)
    return result

def decode_fixed64(data, count):
    result = []
    pos = 0
    for _ in range(count):
        val = struct.unpack_from('<Q', data, pos)[0]
        pos += 8
        result.append(val)
    return result, pos

# Test with value 0
encoded = encode_fixed64([0, 1, 2])
print(f"Encoded [0, 1, 2]: {encoded.hex()}")
decoded, _ = decode_fixed64(encoded, 3)
print(f"Decoded: {decoded}")

# Test what happens with negative index in segment_names list
segment_names = ["node0", "node1", "node2"]
segment_id = 0
print(f"\nsegment_names[{segment_id}] = {segment_names[segment_id] if 0 <= segment_id < len(segment_names) else 'OUT OF BOUNDS'}")

# Test the condition from the code
from_id = 0
condition = f"0 < {from_id} <= {len(segment_names)} = {0 < from_id <= len(segment_names)}"
print(f"\nCondition check for from_id={from_id}: {condition}")
print(f"Would use: {'segment_names[from_id - 1]' if 0 < from_id <= len(segment_names) else f'node_{from_id}'}")
