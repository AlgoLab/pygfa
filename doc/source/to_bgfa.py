#!/usr/bin/env python3

import argparse
import sys
from pygfa.gfa import GFA


# AI! add options to choose the compression method for each component of the
# compressed file. The value of each option is a string with default the empty string.
# The components are:
# 1.  segment_names_header
# 2.  segment_names_payload_lengths
# 3.  segment_names_payload_names
# 4.  segments_header
# 5.  segments_payload_lengths
# 6.  segments_payload_strings
# 7.  links_header
# 8.  links_payload_from
# 9.  links_payload_to
# 10. links_payload_cigar_lengths
# 11. links_payload_cigar
# 12. paths_header
# 13. paths_payload_names
# 14. paths_payload_segment_lengths
# 15. paths_payload_path_ids
# 16. paths_payload_cigar_lengths
# 17. paths_payload_cigar
# 18. walks_header
# 19. walks_payload_sample_ids
# 20. walks_payload_hep_indices
# 21. walks_payload_sequence_ids
# 22. walks_payload_start
# 23. walks_payload_end
# 24. walks_payload_walks
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
