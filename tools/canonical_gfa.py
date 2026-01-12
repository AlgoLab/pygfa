#!/usr/bin/env python3
"""
Canonical GFA writer

This program reads a GFA file and writes a canonical version of it.
The canonical format orders elements as follows:
1. Header
2. Segments (sorted by name)
3. Links (sorted by From, then To)
4. Paths (sorted by PathName)
5. Walks (sorted by SampleID, then SeqId)
6. Containments (sorted by Container, then Contained)

Usage: python canonical_gfa.py <input.gfa> [output.gfa]
       python canonical_gfa.py --verbose <input.gfa> [output.gfa]
"""

import sys
import os
import argparse

# Add the project root to the Python path to ensure imports work correctly
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from pygfa.gfa import GFA
from pygfa.graph_element.parser import header, segment, link, containment, path, line


def parse_gfa_file(filepath):
    """Parse a GFA file and return a GFA object."""
    return GFA.from_gfa(filepath)


def get_header_lines(gfa):
    """Extract header lines from GFA object."""
    # For now, we'll create a basic header
    # In a full implementation, we'd extract from the GFA object
    return ["H\tVN:Z:1.0"]


def get_segment_lines(gfa):
    """Extract segment lines from GFA object, sorted by name."""
    segments = []
    for node_id, data in gfa.nodes_iter(data=True):
        # Build segment line
        line_parts = ["S", node_id, data.get('sequence', '*')]
        
        # Add optional fields
        for key, value in data.items():
            if key not in ['nid', 'sequence', 'slen']:
                # Determine type based on value
                if isinstance(value, int):
                    line_parts.append(f"{key}:i:{value}")
                elif isinstance(value, str):
                    line_parts.append(f"{key}:Z:{value}")
        
        segments.append("\t".join(line_parts))
    
    # Sort by segment name
    segments.sort(key=lambda x: x.split('\t')[1])
    return segments


def get_link_lines(gfa):
    """Extract link lines from GFA object, sorted by From then To."""
    links = []
    for u, v, key, data in gfa.edges_iter(data=True, keys=True):
        if data.get('is_dovetail', False):
            # Build link line
            from_node = data.get('from_node', u)
            from_orn = data.get('from_orn', '+')
            to_node = data.get('to_node', v)
            to_orn = data.get('to_orn', '+')
            alignment = data.get('alignment', '*')
            
            line_parts = ["L", from_node, from_orn, to_node, to_orn, alignment]
            
            # Add optional fields
            for field_name, value in data.items():
                if field_name not in ['eid', 'from_node', 'from_orn', 'to_node', 
                                     'to_orn', 'alignment', 'distance', 'variance', 
                                     'is_dovetail', 'from_positions', 'to_positions',
                                     'from_segment_end', 'to_segment_end']:
                    if isinstance(value, int):
                        line_parts.append(f"{field_name}:i:{value}")
                    elif isinstance(value, str):
                        line_parts.append(f"{field_name}:Z:{value}")
            
            links.append("\t".join(line_parts))
    
    # Sort by From, then To
    links.sort(key=lambda x: (x.split('\t')[2], x.split('\t')[4]))
    return links


def get_path_lines(gfa):
    """Extract path lines from GFA object, sorted by PathName."""
    paths = []
    for path_id, path_data in gfa.paths_iter(data=True):
        # Build path line
        line_parts = ["P", path_id]
        
        # Add segments
        segments = path_data.get('segments', [])
        line_parts.append(",".join(segments))
        
        # Add overlaps
        overlaps = path_data.get('overlaps', [])
        if overlaps:
            line_parts.append(",".join(overlaps))
        
        # Add optional fields
        for key, value in path_data.items():
            if key not in ['path_name', 'segments', 'overlaps']:
                if isinstance(value, int):
                    line_parts.append(f"{key}:i:{value}")
                elif isinstance(value, str):
                    line_parts.append(f"{key}:Z:{value}")
        
        paths.append("\t".join(line_parts))
    
    # Sort by PathName
    paths.sort(key=lambda x: x.split('\t')[1])
    return paths


def get_walk_lines(gfa):
    """Extract walk lines from GFA object, sorted by SampleID then SeqId."""
    walks = []
    for walk_id, walk_data in gfa.walks_iter(data=True):
        # Build walk line
        line_parts = ["W"]
        
        # Add required fields
        line_parts.append(walk_data.get('sample_id', ''))
        line_parts.append(str(walk_data.get('hapindex', 0)))
        line_parts.append(walk_data.get('seq_id', ''))
        
        # Add optional positions
        seq_start = walk_data.get('seq_start', '*')
        seq_end = walk_data.get('seq_end', '*')
        line_parts.append(str(seq_start) if seq_start is not None else '*')
        line_parts.append(str(seq_end) if seq_end is not None else '*')
        
        # Add walk string
        line_parts.append(walk_data.get('walk', ''))
        
        # Add optional fields
        for key, value in walk_data.items():
            if key not in ['sample_id', 'hapindex', 'seq_id', 
                          'seq_start', 'seq_end', 'walk']:
                if isinstance(value, int):
                    line_parts.append(f"{key}:i:{value}")
                elif isinstance(value, str):
                    line_parts.append(f"{key}:Z:{value}")
        
        walks.append("\t".join(line_parts))
    
    # Sort by SampleID, then SeqId
    walks.sort(key=lambda x: (x.split('\t')[1], x.split('\t')[3]))
    return walks


def get_containment_lines(gfa):
    """Extract containment lines from GFA object, sorted by Container then Contained."""
    # For now, return empty list as containments are not yet fully supported
    return []


def write_canonical_gfa(gfa, output_file=None, verbose=False):
    """Write a canonical version of the GFA to a file or stdout."""
    
    if verbose:
        print("Extracting elements from GFA graph...")
    
    # Get all elements in canonical order
    header_lines = get_header_lines(gfa)
    if verbose:
        print(f"  - Found {len(header_lines)} header line(s)")
    
    segment_lines = get_segment_lines(gfa)
    if verbose:
        print(f"  - Found {len(segment_lines)} segment line(s)")
    
    link_lines = get_link_lines(gfa)
    if verbose:
        print(f"  - Found {len(link_lines)} link line(s)")
    
    path_lines = get_path_lines(gfa)
    if verbose:
        print(f"  - Found {len(path_lines)} path line(s)")
    
    walk_lines = get_walk_lines(gfa)
    if verbose:
        print(f"  - Found {len(walk_lines)} walk line(s)")
    
    containment_lines = get_containment_lines(gfa)
    if verbose:
        print(f"  - Found {len(containment_lines)} containment line(s)")
    
    # Combine all lines in canonical order
    all_lines = []
    all_lines.extend(header_lines)
    all_lines.extend(segment_lines)
    all_lines.extend(link_lines)
    all_lines.extend(path_lines)
    all_lines.extend(walk_lines)
    all_lines.extend(containment_lines)
    
    # Write to output
    if output_file:
        if verbose:
            print(f"Writing canonical GFA to {output_file}...")
        with open(output_file, 'w') as f:
            for line in all_lines:
                f.write(line + '\n')
        if verbose:
            print(f"Successfully wrote {len(all_lines)} lines to {output_file}")
    else:
        if verbose:
            print("Writing canonical GFA to stdout...")
        for line in all_lines:
            print(line)
    
    return len(all_lines)


def main():
    parser = argparse.ArgumentParser(
        description="Write a canonical version of a GFA file",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Canonical format ordering:
  1. Header
  2. Segments (sorted by name)
  3. Links (sorted by From, then To)
  4. Paths (sorted by PathName)
  5. Walks (sorted by SampleID, then SeqId)
  6. Containments (sorted by Container, then Contained)

Examples:
  python canonical_gfa.py input.gfa
  python canonical_gfa.py input.gfa output.gfa
  python canonical_gfa.py --verbose input.gfa output.gfa
        """
    )
    
    parser.add_argument(
        'input_file',
        help='Input GFA file'
    )
    
    parser.add_argument(
        'output_file',
        nargs='?',
        help='Output GFA file (optional, defaults to stdout)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Print verbose output'
    )
    
    args = parser.parse_args()
    
    # Check if input file exists
    if not os.path.exists(args.input_file):
        print(f"Error: Input file not found: {args.input_file}")
        sys.exit(1)
    
    try:
        if args.verbose:
            print(f"Reading input file: {args.input_file}")
        
        # Parse the input GFA file
        gfa = parse_gfa_file(args.input_file)
        
        if args.verbose:
            print(f"Successfully parsed GFA file")
            print()
        
        # Write canonical version
        line_count = write_canonical_gfa(gfa, args.output_file, args.verbose)
        
        if not args.verbose:
            if args.output_file:
                print(f"Successfully wrote {line_count} lines to {args.output_file}")
            else:
                print(f"Successfully wrote {line_count} lines to stdout")
        
        sys.exit(0)
        
    except Exception as e:
        print(f"Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
