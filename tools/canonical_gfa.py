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
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from pygfa.gfa import GFA
from pygfa.graph_element.parser import header, segment, link, containment, path, line


def parse_gfa_file(filepath):
    """Parse a GFA file and return a GFA object."""
    return GFA.from_gfa(filepath)


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
        """,
    )

    parser.add_argument("input_file", help="Input GFA file")

    parser.add_argument(
        "output_file", nargs="?", help="Output GFA file (optional, defaults to stdout)"
    )

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Print verbose output"
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

        # AI! use the to_gfa method to write canonical version
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
