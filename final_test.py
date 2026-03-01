#!/usr/bin/env python3

import sys
sys.path.insert(0, '.')

import tempfile
import os
from pygfa.gfa import GFA
from pygfa.bgfa import INTEGER_ENCODING_FIXED64, STRING_ENCODING_NONE

def run_test():
    """Run the specific test case that was failing."""
    gfa_file = 'data/check_overlap_test_no_fasta.gfa'
    
    print(f"Testing file: {gfa_file}")
    print(f"Encoding: fixed64 integer, none string")
    
    # Load original
    g = GFA.from_gfa(gfa_file)
    print(f"Original graph: {len(g.nodes())} nodes, {len(g.edges())} edges")
    
    # Write to bgfa
    with tempfile.NamedTemporaryFile(suffix='.bgfa', delete=False) as tmp:
        bgfa_path = tmp.name
    
    try:
        compression_options = {
            'links_fromto_int_encoding': INTEGER_ENCODING_FIXED64,
            'links_cigars_int_encoding': INTEGER_ENCODING_FIXED64,
            'links_cigars_str_encoding': STRING_ENCODING_NONE,
            'segment_names_int_encoding': INTEGER_ENCODING_FIXED64,
            'segment_names_str_encoding': STRING_ENCODING_NONE,
            'segments_int_encoding': INTEGER_ENCODING_FIXED64,
            'segments_str_encoding': STRING_ENCODING_NONE,
            'paths_names_int_encoding': INTEGER_ENCODING_FIXED64,
            'paths_names_str_encoding': STRING_ENCODING_NONE,
            'paths_cigars_int_encoding': INTEGER_ENCODING_FIXED64,
            'paths_cigars_str_encoding': STRING_ENCODING_NONE,
        }
        
        print("\nWriting BGFA file...")
        g.to_bgfa(bgfa_path, block_size=1024, compression_options=compression_options, 
                  verbose=False, debug=False, logfile=None)
        
        print("Reading BGFA file back...")
        h = GFA.from_bgfa(bgfa_path, verbose=False, debug=False, logfile=None)
        
        print(f"\nDecoded graph: {len(h.nodes())} nodes, {len(h.edges())} edges")
        
        # Check results
        if len(g.nodes()) != len(h.nodes()):
            print(f"FAILED: Node count mismatch: {len(g.nodes())} vs {len(h.nodes())}")
            original_nodes = set(g.nodes())
            decoded_nodes = set(h.nodes())
            print(f"Missing in decoded: {original_nodes - decoded_nodes}")
            print(f"Extra in decoded: {decoded_nodes - original_nodes}")
            return False
        elif len(g.edges()) != len(h.edges()):
            print(f"FAILED: Edge count mismatch: {len(g.edges())} vs {len(h.edges())}")
            return False
        else:
            print("SUCCESS: Graph roundtrip successful!")
            return True
            
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        if os.path.exists(bgfa_path):
            os.unlink(bgfa_path)

if __name__ == "__main__":
    success = run_test()
    sys.exit(0 if success else 1)
