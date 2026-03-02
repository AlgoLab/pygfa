#!/usr/bin/env python3

import os
import sys
import struct
import tempfile

sys.path.insert(0, '.')

from pygfa.gfa import GFA
from pygfa.bgfa import INTEGER_ENCODING_FIXED64, STRING_ENCODING_NONE

def examine_bgfa():
    gfa_file = 'data/check_overlap_test_no_fasta.gfa'
    
    # Load original
    g = GFA.from_gfa(gfa_file)
    
    # Write to bgfa
    with tempfile.NamedTemporaryFile(suffix='.bgfa', delete=False) as tmp:
        bgfa_path = tmp.name
    
    try:
        compression_options = {
            "links_fromto_int_encoding": INTEGER_ENCODING_FIXED64,
            "links_cigars_int_encoding": INTEGER_ENCODING_FIXED64,
            "links_cigars_str_encoding": STRING_ENCODING_NONE,
            "segment_names_int_encoding": INTEGER_ENCODING_FIXED64,
            "segment_names_str_encoding": STRING_ENCODING_NONE,
            "segments_int_encoding": INTEGER_ENCODING_FIXED64,
            "segments_str_encoding": STRING_ENCODING_NONE,
            "paths_names_int_encoding": INTEGER_ENCODING_FIXED64,
            "paths_names_str_encoding": STRING_ENCODING_NONE,
            "paths_cigars_int_encoding": INTEGER_ENCODING_FIXED64,
            "paths_cigars_str_encoding": STRING_ENCODING_NONE,
        }
        
        g.to_bgfa(bgfa_path, block_size=1024, compression_options=compression_options, 
                  verbose=False, debug=False, logfile=None)
        
        # Read and examine the binary file
        with open(bgfa_path, 'rb') as f:
            data = f.read()
        
        print(f"BGFA file size: {len(data)} bytes")
        
        # Try to parse it manually
        pos = 0
        
        # Read magic
        magic = struct.unpack_from('<4s', data, pos)[0]
        pos += 4
        print(f"Magic: {magic}")
        
        # Read version
        version = struct.unpack_from('<H', data, pos)[0]
        pos += 2
        print(f"Version: {version}")
        
        # Read flags
        flags = struct.unpack_from('<H', data, pos)[0]
        pos += 2
        print(f"Flags: {flags:#06x}")
        
        # Read block size
        block_size = struct.unpack_from('<Q', data, pos)[0]
        pos += 8
        print(f"Block size: {block_size}")
        
        # Read until we find segment names block
        while pos < len(data):
            block_type = struct.unpack_from('<B', data, pos)[0]
            pos += 1
            
            if block_type == 1:  # SECTION_ID_SEGMENT_NAMES
                print(f"\nFound segment names block at offset {pos-1}")
                record_num = struct.unpack_from('<H', data, pos)[0]
                pos += 2
                compression_code = struct.unpack_from('<H', data, pos)[0]
                pos += 2
                compressed_len = struct.unpack_from('<Q', data, pos)[0]
                pos += 8
                uncompressed_len = struct.unpack_from('<Q', data, pos)[0]
                pos += 8
                
                print(f"Record num: {record_num}")
                print(f"Compression code: {compression_code:#06x}")
                print(f"Compressed len: {compressed_len}")
                print(f"Uncompressed len: {uncompressed_len}")
                
                # Read payload
                payload = data[pos:pos+compressed_len]
                print(f"Payload length: {len(payload)}")
                
                # Check if it's fixed64
                int_code = (compression_code >> 8) & 0xFF
                str_code = compression_code & 0xFF
                print(f"Integer code: {int_code:#04x} ({int_code})")
                print(f"String code: {str_code:#04x} ({str_code})")
                
                if int_code == 0x0B:  # FIXED64
                    print("\nFixed64 encoded lengths:")
                    # Each length is 8 bytes
                    for i in range(0, min(record_num * 8, 100), 8):
                        if i + 8 <= len(payload):
                            length_val = struct.unpack_from('<Q', payload, i)[0]
                            print(f"  Length[{i//8}]: {length_val}")
                
                break
            
            else:
                # Skip this block - need to read its header
                record_num = struct.unpack_from('<H', data, pos)[0]
                pos += 2
                compression_code = struct.unpack_from('<H', data, pos)[0]
                pos += 2
                compressed_len = struct.unpack_from('<Q', data, pos)[0]
                pos += 8
                uncompressed_len = struct.unpack_from('<Q', data, pos)[0]
                pos += 8
                pos += compressed_len  # Skip payload
        
    finally:
        if os.path.exists(bgfa_path):
            os.unlink(bgfa_path)

if __name__ == "__main__":
    examine_bgfa()
