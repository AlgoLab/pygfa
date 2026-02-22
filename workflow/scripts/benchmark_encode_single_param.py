#!/usr/bin/env python3
"""
Single-parameter benchmark BGFA encoding: GFA -> BGFA with block statistics.

This script is specialized for single-parameter benchmarks where only one
aspect of encoding is varied at a time.

Usage:
    python benchmark_encode_single_param.py --input-gfa input.gfa --output-bgfa output.bgfa --output-csv output.csv [options]

Options:
    --section SECTION     Target a specific section (e.g., segments_payload_strings)
    --int-flag ENC       Integer encoding method (default: identity)
    --str-flag ENC       String encoding method (default: identity)
    --block-size SIZE     Block size (default: 1024)
    --block-type TYPE    Block type: segments, links, paths, walks
"""

import argparse
import subprocess
import sys
import os


SECTION_INT_ENCODINGS = {
    "segment_names_payload_lengths",
    "segments_payload_lengths",
    "links_payload_from",
    "links_payload_to",
    "links_payload_cigar_lengths",
    "paths_payload_segment_lengths",
    "paths_payload_cigar_lengths",
    "walks_payload_hep_indices",
    "walks_payload_start",
    "walks_payload_end",
}

SECTION_STR_ENCODINGS = {
    "segment_names_header",
    "segment_names_payload_names",
    "segments_header",
    "segments_payload_strings",
    "links_header",
    "links_payload_cigar",
    "paths_header",
    "paths_payload_names",
    "paths_payload_path_ids",
    "paths_payload_cigar",
    "walks_header",
    "walks_payload_sample_ids",
    "walks_payload_sequence_ids",
    "walks_payload_walks",
}


def parse_args():
    parser = argparse.ArgumentParser(description="Single-parameter BGFA encoding benchmark")
    parser.add_argument("--input-gfa", "-i", required=True, help="Input GFA file path")
    parser.add_argument("--output-bgfa", "-o", required=True, help="Output BGFA file path")
    parser.add_argument("--output-csv", "-c", required=True, help="Output CSV file path")
    parser.add_argument(
        "--section", "-s", default=None, help="Target a specific section (e.g., segments_payload_strings)"
    )
    parser.add_argument("--int-flag", "-e", default="", help="Integer encoding method (default: identity/empty)")
    parser.add_argument("--str-flag", "-t", default="", help="String encoding method (default: identity/empty)")
    parser.add_argument("--block-size", "-b", type=int, default=1024, help="Block size (default: 1024)")
    parser.add_argument("--block-type", default=None, help="Block type: segments, links, paths, walks")
    return parser.parse_args()


def build_command(args):
    cmd = [
        "pixi",
        "run",
        "python",
        "bin/bgfatools",
        "bgfa",
        args.input_gfa,
        args.output_bgfa,
        "--block-size",
        str(args.block_size),
    ]

    if args.section:
        section = args.section
        int_flag = args.int_flag if section in SECTION_INT_ENCODINGS else ""
        str_flag = args.str_flag if section in SECTION_STR_ENCODINGS else ""

        if section == "segment_names_header":
            cmd.extend(["--segment-names-header", str_flag])
        elif section == "segment_names_payload_lengths":
            cmd.extend(["--segment-names-payload-lengths", int_flag])
        elif section == "segment_names_payload_names":
            cmd.extend(["--segment-names-payload-names", str_flag])
        elif section == "segments_header":
            cmd.extend(["--segments-header", str_flag])
        elif section == "segments_payload_lengths":
            cmd.extend(["--segments-payload-lengths", int_flag])
        elif section == "segments_payload_strings":
            cmd.extend(["--segments-payload-strings", str_flag])
        elif section == "links_header":
            cmd.extend(["--links-header", str_flag])
        elif section == "links_payload_from":
            cmd.extend(["--links-payload-from", int_flag])
        elif section == "links_payload_to":
            cmd.extend(["--links-payload-to", int_flag])
        elif section == "links_payload_cigar_lengths":
            cmd.extend(["--links-payload-cigar-lengths", int_flag])
        elif section == "links_payload_cigar":
            cmd.extend(["--links-payload-cigar", str_flag])
        elif section == "paths_header":
            cmd.extend(["--paths-header", str_flag])
        elif section == "paths_payload_names":
            cmd.extend(["--paths-payload-names", str_flag])
        elif section == "paths_payload_segment_lengths":
            cmd.extend(["--paths-payload-segment-lengths", int_flag])
        elif section == "paths_payload_path_ids":
            cmd.extend(["--paths-payload-path-ids", str_flag])
        elif section == "paths_payload_cigar_lengths":
            cmd.extend(["--paths-payload-cigar-lengths", int_flag])
        elif section == "paths_payload_cigar":
            cmd.extend(["--paths-payload-cigar", str_flag])
        elif section == "walks_header":
            cmd.extend(["--walks-header", str_flag])
        elif section == "walks_payload_sample_ids":
            cmd.extend(["--walks-payload-sample-ids", str_flag])
        elif section == "walks_payload_hep_indices":
            cmd.extend(["--walks-payload-hep-indices", int_flag])
        elif section == "walks_payload_sequence_ids":
            cmd.extend(["--walks-payload-sequence-ids", str_flag])
        elif section == "walks_payload_start":
            cmd.extend(["--walks-payload-start", int_flag])
        elif section == "walks_payload_end":
            cmd.extend(["--walks-payload-end", int_flag])
        elif section == "walks_payload_walks":
            cmd.extend(["--walks-payload-walks", str_flag])
        else:
            print(f"Error: Unknown section '{section}'", file=sys.stderr)
            sys.exit(1)
    elif args.block_type:
        block_type = args.block_type
        int_flag = args.int_flag
        str_flag = args.str_flag
        if block_type == "segments":
            cmd.extend(
                [
                    "--segments-header",
                    str_flag,
                    "--segments-payload-lengths",
                    int_flag,
                    "--segments-payload-strings",
                    str_flag,
                ]
            )
        elif block_type == "links":
            cmd.extend(
                [
                    "--links-header",
                    str_flag,
                    "--links-payload-from",
                    int_flag,
                    "--links-payload-to",
                    int_flag,
                    "--links-payload-cigar-lengths",
                    int_flag,
                    "--links-payload-cigar",
                    str_flag,
                ]
            )
        elif block_type == "paths":
            cmd.extend(
                [
                    "--paths-header",
                    str_flag,
                    "--paths-payload-names",
                    str_flag,
                    "--paths-payload-segment-lengths",
                    int_flag,
                    "--paths-payload-path-ids",
                    str_flag,
                    "--paths-payload-cigar-lengths",
                    int_flag,
                    "--paths-payload-cigar",
                    str_flag,
                ]
            )
        elif block_type == "walks":
            cmd.extend(
                [
                    "--walks-header",
                    str_flag,
                    "--walks-payload-sample-ids",
                    str_flag,
                    "--walks-payload-hep-indices",
                    int_flag,
                    "--walks-payload-sequence-ids",
                    str_flag,
                    "--walks-payload-start",
                    int_flag,
                    "--walks-payload-end",
                    int_flag,
                    "--walks-payload-walks",
                    str_flag,
                ]
            )
        else:
            print(f"Error: Unknown block type '{block_type}'", file=sys.stderr)
            sys.exit(1)
    else:
        int_flag = args.int_flag
        str_flag = args.str_flag
        cmd.extend(
            [
                "--segment-names-header",
                str_flag,
                "--segment-names-payload-lengths",
                int_flag,
                "--segment-names-payload-names",
                str_flag,
                "--segments-header",
                str_flag,
                "--segments-payload-lengths",
                int_flag,
                "--segments-payload-strings",
                str_flag,
                "--links-header",
                str_flag,
                "--links-payload-from",
                int_flag,
                "--links-payload-to",
                int_flag,
                "--links-payload-cigar-lengths",
                int_flag,
                "--links-payload-cigar",
                str_flag,
                "--paths-header",
                str_flag,
                "--paths-payload-names",
                str_flag,
                "--paths-payload-segment-lengths",
                int_flag,
                "--paths-payload-path-ids",
                str_flag,
                "--paths-payload-cigar-lengths",
                int_flag,
                "--paths-payload-cigar",
                str_flag,
                "--walks-header",
                str_flag,
                "--walks-payload-sample-ids",
                str_flag,
                "--walks-payload-hep-indices",
                int_flag,
                "--walks-payload-sequence-ids",
                str_flag,
                "--walks-payload-start",
                int_flag,
                "--walks-payload-end",
                int_flag,
                "--walks-payload-walks",
                str_flag,
            ]
        )

    return cmd


def main():
    args = parse_args()

    os.makedirs(os.path.dirname(args.output_bgfa), exist_ok=True)
    os.makedirs(os.path.dirname(args.output_csv), exist_ok=True)

    cmd = build_command(args)

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"ERROR: Encoding failed for {args.input_gfa}", file=sys.stderr)
        print(f"Command: {' '.join(cmd)}", file=sys.stderr)
        print(f"stdout: {result.stdout}", file=sys.stderr)
        print(f"stderr: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    measure_cmd = [
        "pixi",
        "run",
        "python",
        "bin/bgfatools",
        "measure",
        args.output_bgfa,
        args.output_csv,
        "--original-gfa",
        args.input_gfa,
    ]

    measure_result = subprocess.run(measure_cmd, capture_output=True, text=True)

    if measure_result.returncode != 0:
        print(f"ERROR: Measurement failed for {args.output_bgfa}", file=sys.stderr)
        print(f"Command: {' '.join(measure_cmd)}", file=sys.stderr)
        print(f"stdout: {measure_result.stdout}", file=sys.stderr)
        print(f"stderr: {measure_result.stderr}", file=sys.stderr)
        sys.exit(1)

    print(f"Successfully encoded {args.input_gfa} -> {args.output_bgfa}")
    print(f"Block statistics written to {args.output_csv}")


if __name__ == "__main__":
    main()
