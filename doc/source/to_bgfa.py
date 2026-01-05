#!/usr/bin/env python3

import argparse
import sys
from pygfa.gfa import GFA


def main():
    parser = argparse.ArgumentParser(description="Convert GFA file to BGFA format")
    parser.add_argument("input_file", help="Path to input GFA file")
    parser.add_argument("output_file", help="Path to output BGFA file")
    parser.add_argument(
        "--block-size",
        type=int,
        default=1024,
        help="Block size for BGFA format (default: 1024)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", 
        help="Enable verbose output"
    )
    parser.add_argument(
        "--help", action="store_true", help="Show usage example and exit"
    )
    args = parser.parse_args()

    if args.help:
        print("Usage example:")
        print("  python to_bgfa.py input.gfa output.bgfa")
        print("  python to_bgfa.py input.gfa output.bgfa --block-size 2048")
        sys.exit(0)

    try:
        # Read GFA file
        g = GFA.from_file(args.input_file)

        # Write BGFA file
        g.write_bgfa(args.output_file, block_size=args.block_size)

        if args.verbose:
            print(f"Successfully converted {args.input_file} to {args.output_file}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
