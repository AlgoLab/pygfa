#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, '.')

# Mock the imports that fail
import types
mock_lark = types.ModuleType('lark')
sys.modules['lark'] = mock_lark

try:
    from pygfa.gfa import GFA
    from pygfa.bgfa import INTEGER_ENCODING_FIXED64, STRING_ENCODING_IDENTITY, make_compression_code
    
    # Load the GFA file
    gfa_path = 'data/check_overlap_test_no_fasta.gfa'
    g = GFA.from_gfa(gfa_path)
    print(f'Original nodes: {len(g.nodes())}')
    print('Original node IDs:', sorted(g.nodes(), key=lambda x: int(x) if x.isdigit() else x))
    
    # Try to write with fixed64 encoding
    compression_options = {
        "segment_names_int_encoding": INTEGER_ENCODING_FIXED64,
        "segment_names_str_encoding": STRING_ENCODING_IDENTITY,
        "segments_int_encoding": INTEGER_ENCODING_FIXED64,
        "segments_str_encoding": STRING_ENCODING_IDENTITY,
    }
    
    import tempfile
    with tempfile.NamedTemporaryFile(suffix='.bgfa', delete=False) as f:
        bgfa_path = f.name
    
    try:
        g.to_bgfa(bgfa_path, 1024, compression_options, verbose=False, debug=False, logfile=None)
        print(f"Written BGFA file: {bgfa_path}")
        
        # Try to read it back
        h = GFA.from_bgfa(bgfa_path, verbose=False, debug=False, logfile=None)
        print(f'Roundtrip nodes: {len(h.nodes())}')
        print('Roundtrip node IDs:', sorted(h.nodes(), key=lambda x: int(x) if x.isdigit() else x))
        
        # Compare
        g_nodes = set(g.nodes())
        h_nodes = set(h.nodes())
        print(f'Missing in roundtrip: {g_nodes - h_nodes}')
        print(f'Extra in roundtrip: {h_nodes - g_nodes}')
        
    finally:
        if os.path.exists(bgfa_path):
            os.unlink(bgfa_path)
            
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
