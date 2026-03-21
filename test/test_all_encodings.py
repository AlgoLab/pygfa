#!/usr/bin/env python3
"""Verification script for all encoding strategies.

Tests that every integer and string encoding strategy can be activated
via the bgfatools CLI and performs a successful roundtrip (encode -> decode).

Tests are run in sequential order by encoding type (grouping all fields for
each encoding together). Script exits immediately with non-zero code on first
failure (fail-fast behavior).

Usage:
    pixi run python test/test_all_encodings.py
    pixi run python test/test_all_encodings.py --int-only
    pixi run python test/test_all_encodings.py --str-only
    pixi run python test/test_all_encodings.py --verbose
"""

import argparse
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pygfa.encoding import (
    INTEGER_ENCODINGS,
    STRING_ENCODINGS,
)

FIELD_TO_CLI_INT = {
    "segment_names_payload_lengths": "--names-enc",
    "segments_payload_lengths": "--seq-enc",
    "links_payload_from": "--links-fromto-enc",
    "links_payload_to": "--links-fromto-enc",
    "links_payload_cigar_lengths": "--links-cigars-enc",
    "paths_payload_segment_lengths": "--paths-paths-enc",
    "paths_payload_cigar_lengths": "--paths-cigars-enc",
    "walks_payload_hep_indices": "--walks-hap-indices-enc",
    "walks_payload_start": "--walks-start-enc",
    "walks_payload_end": "--walks-end-enc",
}

FIELD_TO_CLI_STR = {
    "segment_names_header": "--names-enc",
    "segment_names_payload_names": "--names-enc",
    "segments_header": "--seq-enc",
    "segments_payload_strings": "--seq-enc",
    "links_header": "--links-fromto-enc",
    "links_payload_cigar": "--links-cigars-enc",
    "paths_header": "--paths-names-enc",
    "paths_payload_names": "--paths-names-enc",
    "paths_payload_path_ids": "--paths-paths-enc",
    "paths_payload_cigar": "--paths-cigars-enc",
    "walks_header": "--walks-sample-ids-enc",
    "walks_payload_sample_ids": "--walks-sample-ids-enc",
    "walks_payload_sequence_ids": "--walks-seq-ids-enc",
    "walks_payload_walks": "--walks-walks-enc",
}


@dataclass
class TestResult:
    """Result of a single encoding test."""

    encoding_name: str
    field_name: str
    status: str
    error_message: str | None = None
    encode_time_ms: float = 0.0
    decode_time_ms: float = 0.0


@dataclass
class VerificationReport:
    """Collection of all test results."""

    results: list[TestResult] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0
    first_failure: TestResult | None = None

    @property
    def total_time_seconds(self) -> float:
        """Total verification time in seconds."""
        return self.end_time - self.start_time

    @property
    def passed(self) -> int:
        """Count of PASS results."""
        return sum(1 for r in self.results if r.status == "PASS")

    @property
    def failed(self) -> int:
        """Count of FAIL results."""
        return sum(1 for r in self.results if r.status == "FAIL")

    @property
    def skipped(self) -> int:
        """Count of SKIP results."""
        return sum(1 for r in self.results if r.status == "SKIP")

    @property
    def total(self) -> int:
        """Total number of results."""
        return len(self.results)


def find_test_gfa_files(data_dir: str = "data") -> list[str]:
    """Find GFA files tagged with # test: all_encodings."""
    tagged_files = []
    if not os.path.exists(data_dir):
        return tagged_files

    for filename in os.listdir(data_dir):
        if not filename.endswith((".gfa", ".gfa1", ".gfa2")):
            continue

        filepath = os.path.join(data_dir, filename)
        try:
            with open(filepath, "r") as f:
                for i, line in enumerate(f):
                    if i >= 20:
                        break
                    if line.strip() == "# test: all_encodings":
                        tagged_files.append(filepath)
                        break
        except (OSError, UnicodeDecodeError):
            continue

    return sorted(tagged_files)


def run_roundtrip_test(
    gfa_file: str,
    field_name: str,
    int_enc: str,
    str_enc: str,
    is_int_test: bool,
    verbose: bool = False,
) -> TestResult:
    """Run a single roundtrip test for an encoding combination."""
    enc_format = f"{int_enc}-{str_enc}"
    cli_option = FIELD_TO_CLI_INT.get(field_name) if is_int_test else FIELD_TO_CLI_STR.get(field_name)

    if not cli_option:
        return TestResult(
            encoding_name=enc_format,
            field_name=field_name,
            status="FAIL",
            error_message=f"No CLI option mapping for field: {field_name}",
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        bgfa_file = os.path.join(tmpdir, "test.bgfa")
        gfa_output = os.path.join(tmpdir, "test.gfa")

        encode_cmd = [
            "pixi",
            "run",
            "python",
            "bin/bgfatools",
            "bgfa",
            gfa_file,
            bgfa_file,
            cli_option,
            enc_format,
        ]

        encode_start = time.time()
        encode_result = subprocess.run(encode_cmd, capture_output=True, text=True)
        encode_time = (time.time() - encode_start) * 1000

        if encode_result.returncode != 0:
            error_msg = encode_result.stderr.strip() or encode_result.stdout.strip()
            return TestResult(
                encoding_name=enc_format,
                field_name=field_name,
                status="FAIL",
                error_message=f"Encode failed: {error_msg}",
                encode_time_ms=encode_time,
            )

        decode_cmd = [
            "pixi",
            "run",
            "python",
            "bin/bgfatools",
            "cat",
            bgfa_file,
            "-o",
            gfa_output,
        ]

        decode_start = time.time()
        decode_result = subprocess.run(decode_cmd, capture_output=True, text=True)
        decode_time = (time.time() - decode_start) * 1000

        if decode_result.returncode != 0:
            error_msg = decode_result.stderr.strip() or decode_result.stdout.strip()
            return TestResult(
                encoding_name=enc_format,
                field_name=field_name,
                status="FAIL",
                error_message=f"Decode failed: {error_msg}",
                encode_time_ms=encode_time,
                decode_time_ms=decode_time,
            )

        if not os.path.exists(gfa_output) or os.path.getsize(gfa_output) == 0:
            return TestResult(
                encoding_name=enc_format,
                field_name=field_name,
                status="FAIL",
                error_message="Decoded output is empty or missing",
                encode_time_ms=encode_time,
                decode_time_ms=decode_time,
            )

        return TestResult(
            encoding_name=enc_format,
            field_name=field_name,
            status="PASS",
            encode_time_ms=encode_time,
            decode_time_ms=decode_time,
        )


def validate_encodings_present(
    int_encodings: list[str],
    str_encodings: list[str],
) -> None:
    """Validate all expected encodings are present in the test matrix."""
    expected_int = {
        "none", "varint", "fixed16", "fixed32", "fixed64", "delta",
        "gamma", "omega", "golomb", "rice", "streamvbyte", "vbyte",
        "pfor_delta", "simple8b", "group_varint", "bit_packing",
        "fibonacci", "exp_golomb", "byte_packed", "masked_vbyte",
    }
    expected_str = {
        "none", "zstd", "zstd_dict", "gzip", "lzma", "lz4",
        "brotli", "huffman", "frontcoding", "delta", "dictionary",
        "rle", "cigar", "2bit", "arithmetic", "bwt_huffman",
        "ppm", "superstring_none", "superstring_huffman",
        "superstring_2bit", "superstring_ppm",
    }

    int_set = set(int_encodings)
    str_set = set(str_encodings)

    missing_int = expected_int - int_set
    missing_str = expected_str - str_set

    if missing_int:
        print(f"ERROR: Missing integer encodings in test matrix: {sorted(missing_int)}", file=sys.stderr)
        sys.exit(1)
    if missing_str:
        print(f"ERROR: Missing string encodings in test matrix: {sorted(missing_str)}", file=sys.stderr)
        sys.exit(1)


def run_verification(
    test_int: bool = True,
    test_str: bool = True,
    verbose: bool = False,
) -> VerificationReport:
    """Run verification tests for all encoding strategies.

    Tests are executed in sequential order by encoding type (grouping all
    fields for each encoding together). Script exits immediately with
    non-zero code on first failure (fail-fast behavior).
    """
    report = VerificationReport()
    report.start_time = time.time()

    gfa_files = find_test_gfa_files()
    if not gfa_files:
        print("ERROR: No GFA files found with '# test: all_encodings' tag", file=sys.stderr)
        sys.exit(1)

    gfa_file = gfa_files[0]
    if verbose:
        print(f"Using test file: {gfa_file}")

    int_encodings = sorted([e for e in INTEGER_ENCODINGS.keys() if e])
    str_encodings = sorted([e for e in STRING_ENCODINGS.keys() if e])

    validate_encodings_present(int_encodings, str_encodings)

    int_fields = sorted(FIELD_TO_CLI_INT.keys())
    str_fields = sorted(FIELD_TO_CLI_STR.keys())

    if test_int:
        for int_enc in int_encodings:
            for field_name in int_fields:
                if verbose:
                    print(f"Testing: {int_enc}-none on {field_name}...", end=" ")

                result = run_roundtrip_test(gfa_file, field_name, int_enc, "none", True, verbose)
                report.results.append(result)

                if verbose:
                    print(result.status)

                if result.status == "FAIL":
                    report.first_failure = result
                    report.end_time = time.time()
                    return report

    if test_str:
        for str_enc in str_encodings:
            for field_name in str_fields:
                if verbose:
                    print(f"Testing: none-{str_enc} on {field_name}...", end=" ")

                result = run_roundtrip_test(gfa_file, field_name, "none", str_enc, False, verbose)
                report.results.append(result)

                if verbose:
                    print(result.status)

                if result.status == "FAIL":
                    report.first_failure = result
                    report.end_time = time.time()
                    return report

    report.end_time = time.time()
    return report


def print_report(report: VerificationReport) -> None:
    """Print a human-readable verification report to stdout."""
    print("=" * 60)
    print("Encoding Strategy Verification Report")
    print("=" * 60)
    print()

    int_fields_set = set(FIELD_TO_CLI_INT.keys())
    int_results = [r for r in report.results if r.field_name in int_fields_set]
    str_results = [r for r in report.results if r.field_name not in int_fields_set]

    if int_results:
        unique_int_encs = sorted(set(r.encoding_name for r in int_results))
        print(f"Integer Encodings ({len(unique_int_encs)} strategies):")
        print("-" * 40)
        for result in int_results:
            status_marker = "PASS" if result.status == "PASS" else "FAIL"
            line = f"{status_marker}: {result.encoding_name:<20} on {result.field_name}"
            if result.status == "FAIL" and result.error_message:
                line += f"\n    Error: {result.error_message}"
            print(line)
        print()

    if str_results:
        unique_str_encs = sorted(set(r.encoding_name for r in str_results))
        print(f"String Encodings ({len(unique_str_encs)} strategies):")
        print("-" * 40)
        for result in str_results:
            status_marker = "PASS" if result.status == "PASS" else "FAIL"
            line = f"{status_marker}: {result.encoding_name:<20} on {result.field_name}"
            if result.status == "FAIL" and result.error_message:
                line += f"\n    Error: {result.error_message}"
            print(line)
        print()

    print("=" * 60)
    print(f"Summary: {report.passed}/{report.total} tests passed", end="")
    if report.total > 0:
        print(f" ({report.passed / report.total * 100:.1f}%)")
    else:
        print()
    print(f"Time: {report.total_time_seconds:.1f} seconds")
    print("=" * 60)


def print_failure_report(report: VerificationReport) -> None:
    """Print a failure report and exit immediately (fail-fast)."""
    failure = report.first_failure
    if not failure:
        return

    print("=" * 60, file=sys.stderr)
    print("ERROR: Verification failed at first failure", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(f"Encoding: {failure.encoding_name}", file=sys.stderr)
    print(f"Field: {failure.field_name}", file=sys.stderr)
    if failure.error_message:
        print(f"Error: {failure.error_message}", file=sys.stderr)
    print(f"Test: {report.passed}/{report.passed + report.failed} passed", file=sys.stderr)
    print("=" * 60, file=sys.stderr)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Verify all encoding strategies via roundtrip testing"
    )
    parser.add_argument(
        "--int-only",
        action="store_true",
        help="Test only integer encodings",
    )
    parser.add_argument(
        "--str-only",
        action="store_true",
        help="Test only string encodings",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )
    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    args = parse_args()

    test_int = not args.str_only
    test_str = not args.int_only

    report = run_verification(
        test_int=test_int,
        test_str=test_str,
        verbose=args.verbose,
    )

    if report.first_failure:
        print_failure_report(report)
        sys.exit(1)

    print_report(report)
    sys.exit(0)


if __name__ == "__main__":
    main()
