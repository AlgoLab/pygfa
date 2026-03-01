#!/usr/bin/env python3
"""
Benchmark BGFA encoding: GFA -> BGFA with block statistics.

Usage:
    python benchmark_encode.py --input-gfa input.gfa --output-bgfa output.bgfa --output-csv output.csv --int-flag ENC --str-flag ENC
"""

import argparse
import subprocess
import sys
import os


def parse_args():
    parser = argparse.ArgumentParser(description="BGFA encoding benchmark")
    parser.add_argument("--input-gfa", "-i", required=True, help="Input GFA file path")
    parser.add_argument("--output-bgfa", "-o", required=True, help="Output BGFA file path")
    parser.add_argument("--output-csv", "-c", required=True, help="Output CSV file path")
    parser.add_argument("--int-flag", "-e", default="", help="Integer encoding method")
    parser.add_argument("--str-flag", "-t", default="", help="String encoding method")
    return parser.parse_args()


def main():
    args = parse_args()

    gfa_path = args.input_gfa
    bgfa_path = args.output_bgfa
    csv_file = args.output_csv
    int_flag = args.int_flag
    str_flag = args.str_flag

    os.makedirs(os.path.dirname(bgfa_path), exist_ok=True)
    os.makedirs(os.path.dirname(csv_file), exist_ok=True)

    cmd = [
        "pixi",
        "run",
        "python",
        "bin/bgfatools",
        "bgfa",
        gfa_path,
        bgfa_path,
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

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"ERROR: Encoding failed for {gfa_path}", file=sys.stderr)
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
        bgfa_path,
        csv_file + ".tmp",
    ]

    measure_result = subprocess.run(measure_cmd, capture_output=True, text=True)

    if measure_result.returncode != 0:
        print(f"ERROR: Measurement failed for {bgfa_path}", file=sys.stderr)
        print(f"Command: {' '.join(measure_cmd)}", file=sys.stderr)
        print(f"stdout: {measure_result.stdout}", file=sys.stderr)
        print(f"stderr: {measure_result.stderr}", file=sys.stderr)
        sys.exit(1)

    with open(csv_file + ".tmp", "r") as f_in:
        with open(csv_file, "w") as f_out:
            for line in f_in:
                if line.startswith("filename,"):
                    f_out.write("original_gfa," + line)
                else:
                    f_out.write(gfa_path + "," + line)

    os.remove(csv_file + ".tmp")

    print(f"Successfully encoded {gfa_path} -> {bgfa_path}")
    print(f"Block statistics written to {csv_file}")


if __name__ == "__main__":
    main()
