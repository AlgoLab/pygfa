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
        "--verbose", "-v", action="store_true", help="Enable verbose output"
    )
    parser.add_argument(
        "--help", action="store_true", help="Show usage example and exit"
    )
    
    # Compression method options for each component
    parser.add_argument(
        "--segment-names-header",
        type=str,
        default="",
        help="Compression method for segment names header (default: '')",
    )
    parser.add_argument(
        "--segment-names-payload-lengths",
        type=str,
        default="",
        help="Compression method for segment names payload lengths (default: '')",
    )
    parser.add_argument(
        "--segment-names-payload-names",
        type=str,
        default="",
        help="Compression method for segment names payload names (default: '')",
    )
    parser.add_argument(
        "--segments-header",
        type=str,
        default="",
        help="Compression method for segments header (default: '')",
    )
    parser.add_argument(
        "--segments-payload-lengths",
        type=str,
        default="",
        help="Compression method for segments payload lengths (default: '')",
    )
    parser.add_argument(
        "--segments-payload-strings",
        type=str,
        default="",
        help="Compression method for segments payload strings (default: '')",
    )
    parser.add_argument(
        "--links-header",
        type=str,
        default="",
        help="Compression method for links header (default: '')",
    )
    parser.add_argument(
        "--links-payload-from",
        type=str,
        default="",
        help="Compression method for links payload from (default: '')",
    )
    parser.add_argument(
        "--links-payload-to",
        type=str,
        default="",
        help="Compression method for links payload to (default: '')",
    )
    parser.add_argument(
        "--links-payload-cigar-lengths",
        type=str,
        default="",
        help="Compression method for links payload cigar lengths (default: '')",
    )
    parser.add_argument(
        "--links-payload-cigar",
        type=str,
        default="",
        help="Compression method for links payload cigar (default: '')",
    )
    parser.add_argument(
        "--paths-header",
        type=str,
        default="",
        help="Compression method for paths header (default: '')",
    )
    parser.add_argument(
        "--paths-payload-names",
        type=str,
        default="",
        help="Compression method for paths payload names (default: '')",
    )
    parser.add_argument(
        "--paths-payload-segment-lengths",
        type=str,
        default="",
        help="Compression method for paths payload segment lengths (default: '')",
    )
    parser.add_argument(
        "--paths-payload-path-ids",
        type=str,
        default="",
        help="Compression method for paths payload path ids (default: '')",
    )
    parser.add_argument(
        "--paths-payload-cigar-lengths",
        type=str,
        default="",
        help="Compression method for paths payload cigar lengths (default: '')",
    )
    parser.add_argument(
        "--paths-payload-cigar",
        type=str,
        default="",
        help="Compression method for paths payload cigar (default: '')",
    )
    parser.add_argument(
        "--walks-header",
        type=str,
        default="",
        help="Compression method for walks header (default: '')",
    )
    parser.add_argument(
        "--walks-payload-sample-ids",
        type=str,
        default="",
        help="Compression method for walks payload sample ids (default: '')",
    )
    parser.add_argument(
        "--walks-payload-hep-indices",
        type=str,
        default="",
        help="Compression method for walks payload hep indices (default: '')",
    )
    parser.add_argument(
        "--walks-payload-sequence-ids",
        type=str,
        default="",
        help="Compression method for walks payload sequence ids (default: '')",
    )
    parser.add_argument(
        "--walks-payload-start",
        type=str,
        default="",
        help="Compression method for walks payload start (default: '')",
    )
    parser.add_argument(
        "--walks-payload-end",
        type=str,
        default="",
        help="Compression method for walks payload end (default: '')",
    )
    parser.add_argument(
        "--walks-payload-walks",
        type=str,
        default="",
        help="Compression method for walks payload walks (default: '')",
    )
    
    args = parser.parse_args()

    if args.help:
        print("Usage example:")
        print("  python to_bgfa.py input.gfa output.bgfa")
        print("  python to_bgfa.py input.gfa output.bgfa --block-size 2048")
        print("  python to_bgfa.py input.gfa output.bgfa --segments-payload-strings zstd --links-payload-cigar gzip")
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
