#!/usr/bin/env python3
"""Debug script for BGFA node count issue."""

import os
import sys
import tempfile
from pygfa.gfa import GFA


def main():
    gfa_file = "data/check_overlap_test_no_fasta.gfa"

    # Load the original GFA file
    print("Loading original GFA file...")
    g = GFA.from_gfa(gfa_file)

    print(f"Original graph nodes: {len(g.nodes())}")
    print(f"Original graph edges: {len(g.edges())}")

    # Get node IDs and sort them numerically
    g_node_ids = list(g.nodes())
    # Convert to integers for sorting, but keep as strings for graph operations
    g_node_ids_int = [int(nid) for nid in g_node_ids]
    print("Original node IDs (as strings):", g_node_ids)
    print("Original node IDs (as ints, sorted):", sorted(g_node_ids_int))

    # Create compression options for int_fixed64_str_none
    compression_options = {
        "links_fromto_int_encoding": "int_fixed64",
        "links_cigars_int_encoding": "int_fixed64",
        "links_cigars_str_encoding": "str_none",
        "segment_names_int_encoding": "int_fixed64",
        "segment_names_str_encoding": "str_none",
        "segments_int_encoding": "int_fixed64",
        "segments_str_encoding": "str_none",
        "paths_names_int_encoding": "int_fixed64",
        "paths_names_str_encoding": "str_none",
        "paths_cigars_int_encoding": "int_fixed64",
        "paths_cigars_str_encoding": "str_none",
    }

    # Write to BGFA
    print("\nWriting to BGFA...")
    with tempfile.NamedTemporaryFile(suffix=".bgfa", delete=False) as tmp:
        bgfa_path = tmp.name

    try:
        g.to_bgfa(
            bgfa_path,
            block_size=1024,
            compression_options=compression_options,
            verbose=False,
            debug=False,
            logfile=None,
        )

        # Read from BGFA
        print("Reading from BGFA...")
        h = GFA.from_bgfa(bgfa_path, verbose=False, debug=False, logfile=None)

        print(f"Round-trip graph nodes: {len(h.nodes())}")
        print(f"Round-trip graph edges: {len(h.edges())}")
        print("Round-trip node IDs:", sorted([int(nid) for nid in h.nodes()]))

        # Find the difference
        g_nodes = set(g.nodes())
        h_nodes = set(h.nodes())

        print(f"\nOriginal nodes: {g_nodes}")
        print(f"Round-trip nodes: {h_nodes}")

        if len(g_nodes) != len(h_nodes):
            print(f"\nNode count mismatch: {len(g_nodes)} vs {len(h_nodes)}")
            print(f"Extra nodes in round-trip: {h_nodes - g_nodes}")
            print(f"Missing nodes in round-trip: {g_nodes - h_nodes}")

            # Let's check each node's details
            print("\nChecking node details...")
            for nid in sorted(list(h_nodes)):
                if nid in g_nodes:
                    g_node = g.node(nid)
                    h_node = h.node(nid)
                    print(f"Node {nid}: Both graphs have it")
                    if str(g_node) != str(h_node):
                        print(f"  WARNING: Node {nid} differs!")
                        print(f"  Original: {g_node}")
                        print(f"  Round-trip: {h_node}")
                else:
                    print(f"Node {nid}: ONLY in round-trip graph")
                    print(f"  Details: {h.node(nid)}")

    finally:
        # Clean up
        if os.path.exists(bgfa_path):
            os.unlink(bgfa_path)


if __name__ == "__main__":
    main()
