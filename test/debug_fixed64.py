#!/usr/bin/env python3

import os
import sys
import tempfile

sys.path.insert(0, '.')

from pygfa.gfa import GFA
from pygfa.bgfa import INTEGER_ENCODING_FIXED64, STRING_ENCODING_NONE, make_compression_code

def test_fixed64_roundtrip():
    """Test fixed64 encoding roundtrip specifically."""
    gfa_file = 'data/check_overlap_test_no_fasta.gfa'
    
    # Load original
    g = GFA.from_gfa(gfa_file)
    print(f"Original graph: {len(g.nodes())} nodes, {len(g.edges())} edges")
    print(f"Original node IDs: {sorted(list(g.nodes()))}")
    
    # Write to bgfa with fixed64 encoding
    with tempfile.NamedTemporaryFile(suffix='.bgfa', delete=False) as tmp:
        bgfa_path = tmp.name
    
    try:
        # Create compression options
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
        
        # Read back
        h = GFA.from_bgfa(bgfa_path, verbose=False, debug=False, logfile=None)
        
        print(f"\nDecoded graph: {len(h.nodes())} nodes, {len(h.edges())} edges")
        print(f"Decoded node IDs: {sorted(list(h.nodes()))}")
        
        # Compare
        original_nodes = set(g.nodes())
        decoded_nodes = set(h.nodes())
        
        print(f"\nMissing in decoded: {original_nodes - decoded_nodes}")
        print(f"Extra in decoded: {decoded_nodes - original_nodes}")
        
    finally:
        if os.path.exists(bgfa_path):
            os.unlink(bgfa_path)

if __name__ == "__main__":
    test_fixed64_roundtrip()
