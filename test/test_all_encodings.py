#!/usr/bin/env python3
"""Verification script for all encoding strategies.

Tests that every integer and string encoding strategy can be activated
via the bgfatools CLI and performs a successful roundtrip (encode -> decode).

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

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pygfa.encoding import (
    INTEGER_ENCODINGS,
    STRING_ENCODINGS,
)


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


@dataclass
class TestResult:
    """Result of a single encoding test."""

    encoding_name: str
    field_name: str
    status: str  # PASS, FAIL, SKIP
    error_message: str | None = None
    encode_time_ms: float = 0.0
    decode_time_ms: float = 0.0


@dataclass
class VerificationReport:
    """Collection of all test results."""

    results: list[TestResult] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0

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
    """Find GFA files tagged with # test: all_encodings.

    Args:
        data_dir: Directory to search for GFA files.

    Returns:
        List of paths to GFA files with the all_encodings tag.
    """
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


def get_field_cli_option(field_name: str) -> str:
    """Convert field name to CLI option format.

    Args:
        field_name: Field name like 'segment_names_header'.

    Returns:
        CLI option like '--segment-names-header'.
    """
    return "--" + field_name.replace("_", "-")


def run_roundtrip_test(
    gfa_file: str,
    field_name: str,
    int_enc: str,
    str_enc: str,
    verbose: bool = False,
) -> TestResult:
    """Run a single roundtrip test for an encoding combination.

    Args:
        gfa_file: Path to input GFA file.
        field_name: Field to test.
        int_enc: Integer encoding name.
        str_enc: String encoding name.
        verbose: Print verbose output.

    Returns:
        TestResult with status and timing.
    """
    enc_format = f"{int_enc}-{str_enc}"
    cli_option = get_field_cli_option(field_name)

    with tempfile.TemporaryDirectory() as tmpdir:
        bgfa_file = os.path.join(tmpdir, "test.bgfa")
        gfa_output = os.path.join(tmpdir, "test.gfa")

        # Encode
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

        # Decode
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

        # Verify output exists and is non-empty
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


def run_verification(
    test_int: bool = True,
    test_str: bool = True,
    verbose: bool = False,
) -> VerificationReport:
    """Run verification tests for all encoding strategies.

    Args:
        test_int: Test integer encodings.
        test_str: Test string encodings.
        verbose: Print verbose output.

    Returns:
        VerificationReport with all results.
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

    int_encodings = sorted(INTEGER_ENCODINGS.keys())
    str_encodings = sorted(STRING_ENCODINGS.keys())

    # Remove empty string (alias for none)
    int_encodings = [e for e in int_encodings if e]
    str_encodings = [e for e in str_encodings if e]

    # Test integer encodings on integer fields
    if test_int:
        for field_name in sorted(SECTION_INT_ENCODINGS):
            for int_enc in int_encodings:
                if verbose:
                    print(f"Testing: {int_enc}-none on {field_name}...", end=" ")

                result = run_roundtrip_test(gfa_file, field_name, int_enc, "none", verbose)
                report.results.append(result)

                if verbose:
                    print(result.status)

    # Test string encodings on string fields
    if test_str:
        for field_name in sorted(SECTION_STR_ENCODINGS):
            for str_enc in str_encodings:
                if verbose:
                    print(f"Testing: none-{str_enc} on {field_name}...", end=" ")

                result = run_roundtrip_test(gfa_file, field_name, "none", str_enc, verbose)
                report.results.append(result)

                if verbose:
                    print(result.status)

    report.end_time = time.time()
    return report


def print_report(report: VerificationReport) -> None:
    """Print a human-readable verification report to stdout.

    Args:
        report: VerificationReport to print.
    """
    print("=" * 60)
    print("Encoding Strategy Verification Report")
    print("=" * 60)
    print()

    # Group by encoding type
    int_results = [r for r in report.results if r.field_name in SECTION_INT_ENCODINGS]
    str_results = [r for r in report.results if r.field_name in SECTION_STR_ENCODINGS]

    if int_results:
        print(f"Integer Encodings ({len(set(r.encoding_name for r in int_results))} strategies):")
        print("-" * 40)
        for result in int_results:
            status_marker = "PASS" if result.status == "PASS" else "FAIL"
            line = f"{status_marker}: {result.encoding_name:<20} on {result.field_name}"
            if result.status == "FAIL" and result.error_message:
                line += f"\n    Error: {result.error_message}"
            print(line)
        print()

    if str_results:
        print(f"String Encodings ({len(set(r.encoding_name for r in str_results))} strategies):")
        print("-" * 40)
        for result in str_results:
            status_marker = "PASS" if result.status == "PASS" else "FAIL"
            line = f"{status_marker}: {result.encoding_name:<20} on {result.field_name}"
            if result.status == "FAIL" and result.error_message:
                line += f"\n    Error: {result.error_message}"
            print(line)
        print()

    # Summary
    print("=" * 60)
    print(f"Summary: {report.passed}/{report.total} tests passed", end="")
    if report.total > 0:
        print(f" ({report.passed / report.total * 100:.1f}%)")
    else:
        print()
    print(f"Time: {report.total_time_seconds:.1f} seconds")
    print("=" * 60)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(description="Verify all encoding strategies via roundtrip testing")
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

    print_report(report)

    if report.failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
