#!/usr/bin/env python3

import os
import sys
import struct
import tempfile
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

sys.path.insert(0, '.')

from pygfa.gfa import GFA
from pygfa.bgfa import INTEGER_ENCODING_FIXED64, STRING_ENCODING_NONE

def test_with_debug_logging():
    """Test with debug logging to see what's happening."""
    gfa_file = 'data/check_overlap_test_no_fasta.gfa'
    
    # Load original
    g = GFA.from_gfa(gfa_file)
    print(f"Original graph: {len(g.nodes())} nodes, {len(g.edges())} edges")
    
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
        
        # First, let's see what segment map looks like
        segment_names = list(g.nodes())
        print(f"Segment names (sorted): {sorted(segment_names)}")
        print(f"Segment names (as stored): {segment_names}")
        
        # Create a simple segment map like in the writer
        segment_map = {name: idx for idx, name in enumerate(segment_names)}
        print(f"\nSegment map:")
        for name, idx in sorted(segment_map.items()):
            print(f"  '{name}' -> {idx} (stored as {idx + 1})")
        
        # Now let's look at the edges
        print(f"\nEdges in original graph:")
        edges = list(g.edges(data=True))
        for i, (u, v, data) in enumerate(edges[:5]):  # Just first 5
            print(f"  Edge {i}: {u} -> {v}, data: {data}")
        
        # Write the BGFA file
        print(f"\nWriting BGFA file...")
        g.to_bgfa(bgfa_path, block_size=1024, compression_options=compression_options, 
                  verbose=True, debug=True, logfile=None)
        
        # Read it back with debugging
        print(f"\nReading BGFA file back...")
        h = GFA.from_bgfa(bgfa_path, verbose=True, debug=True, logfile=None)
        
    finally:
        if os.path.exists(bgfa_path):
            os.unlink(bgfa_path)

if __name__ == "__main__":
    test_with_debug_logging()
