#!/usr/bin/env python3
"""Characterize a GFA dataset - extract structural properties as JSON.

Usage:
    pixi run python tools/characterize_datasets.py data/example.gfa
"""

import json
import os
import sys

from pygfa.gfa import GFA


def characterize(gfa_path: str) -> dict:
    """Parse a GFA file and return a dict of structural properties."""
    result: dict = {
        "file": gfa_path,
    }

    try:
        result["file_size_bytes"] = os.path.getsize(gfa_path)
        gfa = GFA.from_gfa(gfa_path)
    except Exception as e:
        result["error"] = str(e)
        return result

    n_nodes = len(gfa.nodes())
    n_edges = len(gfa.edges())
    n_paths = len(list(gfa.paths()))
    n_walks = len(list(gfa.walks()))

    result["num_segments"] = n_nodes
    result["num_links"] = n_edges
    result["num_paths"] = n_paths
    result["num_walks"] = n_walks

    # Sequence statistics
    seq_lengths: list[int] = []
    all_chars_seq: set[str] = set()
    atgc_counts: dict[str, int] = {"A": 0, "T": 0, "G": 0, "C": 0}
    for _nid, node_data in gfa.nodes(data=True):
        seq = node_data.get("sequence", "*")
        if seq and seq != "*":
            seq_lengths.append(len(seq))
            for ch in seq.upper():
                all_chars_seq.add(ch)
                if ch in atgc_counts:
                    atgc_counts[ch] += 1

    result["avg_seq_len"] = round(sum(seq_lengths) / len(seq_lengths), 2) if seq_lengths else 0.0
    result["max_seq_len"] = max(seq_lengths) if seq_lengths else 0
    total_atgc = sum(atgc_counts.values())
    result["gc_content"] = round((atgc_counts["G"] + atgc_counts["C"]) / total_atgc, 4) if total_atgc > 0 else 0.0
    result["unique_chars_seq"] = len(all_chars_seq)

    # Name statistics
    all_chars_names: set[str] = set()
    for nid in gfa.nodes():
        for ch in str(nid):
            all_chars_names.add(ch)
    for u, v, key in gfa.edges(keys=True):
        for ch in f"{u}{v}{key}":
            all_chars_names.add(ch)
    for path in gfa.paths():
        for ch in str(getattr(path, "path_id", "")):
            all_chars_names.add(ch)
    result["unique_chars_names"] = len(all_chars_names)

    # CIGAR statistics
    cigar_lens: list[int] = []
    for _u, _v, edge_data in gfa.edges(data=True):
        alignment = edge_data.get("alignment", "*")
        if alignment and alignment != "*":
            cigar_lens.append(len(str(alignment)))
    result["avg_cigar_len"] = round(sum(cigar_lens) / len(cigar_lens), 2) if cigar_lens else 0.0
    result["cigar_present_ratio"] = round(len(cigar_lens) / n_edges, 4) if n_edges else 0.0

    # Path depth
    path_depths: list[int] = []
    for path in gfa.paths():
        seg_ids = getattr(path, "segment_ids", [])
        if seg_ids:
            path_depths.append(len(seg_ids))
    result["avg_path_depth"] = round(sum(path_depths) / len(path_depths), 2) if path_depths else 0.0
    result["max_path_depth"] = max(path_depths) if path_depths else 0

    # Walk statistics
    result["has_walks"] = n_walks > 0

    return result


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: pixi run python tools/characterize_datasets.py <gfa_file>", file=sys.stderr)
        sys.exit(1)

    gfa_path = sys.argv[1]
    result = characterize(gfa_path)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
