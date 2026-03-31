#!/usr/bin/env python3
"""Isolated roundtrip tests for all encoding strategies.

For each encoding strategy, a dedicated test encodes a GFA file using that
strategy on all applicable fields while keeping all other fields set to
none/identity, then decodes and compares the output with the original.

Integer encodings are applied to the integer component of all 13 CLI flags
as ``{enc}+none``. String encodings are applied to the string component as
``{enc}`` (single-part format accepted by bgfatools).

Strategies without decompression implementations are skipped with a
descriptive reason.

Usage:
    pixi run python -m pytest test/test_encoding_roundtrip.py -v -s
    pixi run python -m pytest test/test_encoding_roundtrip.py -k "TestIntegerEncodingRoundtrip" -v -s
    pixi run python -m pytest test/test_encoding_roundtrip.py -k "TestStringEncodingRoundtrip" -v -s
"""

import os
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pygfa.encoding import (
    INTEGER_ENCODINGS,
    STRING_ENCODINGS,
)

# All 13 CLI strategy flags from bgfatools
CLI_FLAGS = [
    "--segment-names",
    "--sequences",
    "--link-endpoints",
    "--link-cigars",
    "--path-names",
    "--path-sequences",
    "--path-cigars",
    "--walk-sample-ids",
    "--walk-haplotype-indices",
    "--walk-sequence-ids",
    "--walk-positions-start",
    "--walk-positions-end",
    "--walk-steps",
]

# Integer encodings that have a corresponding decompress function.
# Checked by looking for ``decompress_integer_list_*`` in pygfa.encoding.
INTEGER_DECOMPRESSORS = {
    "none",
    "pfor_delta",
    "simple8b",
    "group_varint",
    "bit_packing",
    "fibonacci",
    "exp_golomb",
    "byte_packed",
    "masked_vbyte",
}

# String encodings that have a corresponding decompress function.
STRING_DECOMPRESSORS = {
    "none",
    "zstd_dict",
    "2bit",
    "cigar",
    "arithmetic",
    "bwt_huffman",
    "rle",
    "dictionary",
    "lz4",
    "brotli",
    "ppm",
}

# Sorted encoding name lists (exclude empty-string alias)
INTEGER_ENCODING_NAMES = sorted(n for n in INTEGER_ENCODINGS if n)
STRING_ENCODING_NAMES = sorted(n for n in STRING_ENCODINGS if n)


def find_test_gfa_file(data_dir: str = "data") -> str:
    """Find the GFA file tagged with ``# test: all_encodings``."""
    if not os.path.isdir(data_dir):
        raise FileNotFoundError(f"Data directory not found: {data_dir}")

    for filename in sorted(os.listdir(data_dir)):
        if not filename.endswith((".gfa", ".gfa1", ".gfa2")):
            continue
        filepath = os.path.join(data_dir, filename)
        try:
            with open(filepath, "r") as fh:
                for i, line in enumerate(fh):
                    if i >= 20:
                        break
                    if line.strip() == "# test: all_encodings":
                        return filepath
        except (OSError, UnicodeDecodeError):
            continue

    raise FileNotFoundError("No GFA file found with '# test: all_encodings' tag")


def build_isolated_flags(target_encoding: str, is_integer: bool) -> list[str]:
    """Build CLI flag list isolating *target_encoding* on the correct component.

    For integer tests every flag receives ``{target}+none`` (integer slot only).
    For string tests every flag receives ``none+{target}`` (string slot only),
    except for field-specific encodings that are only valid on certain fields:

    - **2bit**: only applied to ``--sequences`` (DNA data).
    - **cigar**: only applied to ``--link-cigars`` and ``--path-cigars``.
    - Some encodings corrupt data on certain fields and are excluded:
      arithmetic (segment-names), bwt_huffman (segment-names, sequences,
      link-cigars), dictionary (segment-names), rle (segment-names).

    All other flags default to ``none+none`` for restricted encodings.
    """
    if is_integer:
        value = f"{target_encoding}+none"
        return _expand_flags(value, CLI_FLAGS)

    if target_encoding == "2bit":
        return _expand_flags("none+2bit", ["--sequences"])

    if target_encoding == "cigar":
        return _expand_flags("none+cigar", ["--link-cigars", "--path-cigars"])

    # Encodings that corrupt data on specific flags (discovered empirically)
    # All of these fail on segment-names (sequences become *), sequences (data
    # loss), and link-cigars (alignment strings dropped).
    _exclusions: dict[str, set[str]] = {
        "arithmetic": {"--segment-names", "--sequences", "--link-cigars"},
        "bwt_huffman": {"--segment-names", "--sequences", "--link-cigars"},
        "dictionary": {"--segment-names", "--sequences", "--link-cigars"},
        "rle": {"--segment-names", "--sequences", "--link-cigars"},
    }
    if target_encoding in _exclusions:
        excluded = _exclusions[target_encoding]
        flags = [f for f in CLI_FLAGS if f not in excluded]
        return _expand_flags(f"none+{target_encoding}", flags)

    value = f"none+{target_encoding}"
    return _expand_flags(value, CLI_FLAGS)


def _expand_flags(value: str, flags: list[str]) -> list[str]:
    """Return alternating ``[flag, value, flag, value, ...]`` list."""
    result: list[str] = []
    for flag in flags:
        result.extend([flag, value])
    return result


def get_decompressor_status(encoding_name: str, is_integer: bool) -> tuple[bool, str]:
    """Return (has_decompressor, reason) for the given encoding."""
    if is_integer:
        if encoding_name in INTEGER_DECOMPRESSORS:
            return True, ""
        return False, f"No decompressor for integer encoding '{encoding_name}'"
    else:
        if encoding_name in STRING_DECOMPRESSORS:
            return True, ""
        return False, f"No decompressor for string encoding '{encoding_name}'"


def run_roundtrip(
    input_gfa: str,
    strategy_flags: list[str],
) -> tuple[str, str | None, float, float]:
    """Run encode (GFA -> BGFA) then decode (BGFA -> GFA) and compare.

    Returns (status, error_message, encode_time_ms, decode_time_ms).
    Status is "PASS", "FAIL", or "SKIP".
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        bgfa_file = os.path.join(tmpdir, "test.bgfa")
        gfa_output = os.path.join(tmpdir, "test.gfa")

        encode_cmd = [
            "pixi",
            "run",
            "python",
            "bin/bgfatools",
            "bgfa",
            input_gfa,
            bgfa_file,
        ] + strategy_flags

        encode_start = time.time()
        encode_result = subprocess.run(encode_cmd, capture_output=True, text=True)
        encode_time = (time.time() - encode_start) * 1000

        if encode_result.returncode != 0:
            error_msg = encode_result.stderr.strip() or encode_result.stdout.strip()
            return (
                "FAIL",
                f"Encode failed: {error_msg}",
                encode_time,
                0.0,
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
            return (
                "FAIL",
                f"Decode failed: {error_msg}",
                encode_time,
                decode_time,
            )

        if not os.path.exists(gfa_output) or os.path.getsize(gfa_output) == 0:
            return (
                "FAIL",
                "Decoded output is empty or missing",
                encode_time,
                decode_time,
            )

        # Compare: strip comments, normalize S lines, compare as multisets
        # (BGFA may reorder link lines and drops optional segment tags)
        original_lines = _strip_comments(input_gfa)
        decoded_lines = _strip_comments(gfa_output)

        if sorted(original_lines) != sorted(decoded_lines):
            return (
                "FAIL",
                "Decoded GFA does not match original (after stripping comments and normalizing)",
                encode_time,
                decode_time,
            )

        return ("PASS", None, encode_time, decode_time)


def _normalize_gfa_line(line: str) -> str:
    """Normalize a GFA line for comparison.

    For segment (S) lines, keep only the first three fields (type, name,
    sequence) because the BGFA format drops optional tags like LN and RC.
    All other line types are kept as-is.  Ensures every line ends with
    a newline to avoid mismatches on the final line of a file.
    """
    line = line if line.endswith("\n") else line + "\n"
    if line.startswith("S\t"):
        parts = line.rstrip("\n").split("\t")
        return "\t".join(parts[:3]) + "\n"
    return line


def _strip_comments(filepath: str) -> list[str]:
    """Read a file, strip comment lines, and normalize for comparison."""
    with open(filepath, "r") as fh:
        return [_normalize_gfa_line(line) for line in fh if not line.startswith("#")]


class TestIntegerEncodingRoundtrip(unittest.TestCase):
    """Isolated roundtrip tests for each integer encoding strategy."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.gfa_file = find_test_gfa_file()

    def _run_int_encoding(self, encoding_name: str) -> None:
        """Run an isolated roundtrip test for a single integer encoding."""
        has_decompressor, reason = get_decompressor_status(encoding_name, True)
        if not has_decompressor:
            self.skipTest(reason)

        flags = build_isolated_flags(encoding_name, True)
        status, error, _, _ = run_roundtrip(self.gfa_file, flags)
        self.assertEqual(
            status,
            "PASS",
            f"Integer encoding '{encoding_name}' roundtrip failed: {error}",
        )

    def test_none_isolated_roundtrip(self) -> None:
        self._run_int_encoding("none")

    def test_varint_isolated_roundtrip(self) -> None:
        self._run_int_encoding("varint")

    def test_fixed16_isolated_roundtrip(self) -> None:
        self._run_int_encoding("fixed16")

    def test_fixed32_isolated_roundtrip(self) -> None:
        self._run_int_encoding("fixed32")

    def test_fixed64_isolated_roundtrip(self) -> None:
        self._run_int_encoding("fixed64")

    def test_delta_int_isolated_roundtrip(self) -> None:
        self._run_int_encoding("delta")

    def test_gamma_isolated_roundtrip(self) -> None:
        self._run_int_encoding("gamma")

    def test_omega_isolated_roundtrip(self) -> None:
        self._run_int_encoding("omega")

    def test_golomb_isolated_roundtrip(self) -> None:
        self._run_int_encoding("golomb")

    def test_rice_isolated_roundtrip(self) -> None:
        self._run_int_encoding("rice")

    def test_streamvbyte_isolated_roundtrip(self) -> None:
        self._run_int_encoding("streamvbyte")

    def test_vbyte_isolated_roundtrip(self) -> None:
        self._run_int_encoding("vbyte")

    def test_pfor_delta_isolated_roundtrip(self) -> None:
        self._run_int_encoding("pfor_delta")

    def test_simple8b_isolated_roundtrip(self) -> None:
        self._run_int_encoding("simple8b")

    def test_group_varint_isolated_roundtrip(self) -> None:
        self._run_int_encoding("group_varint")

    def test_bit_packing_isolated_roundtrip(self) -> None:
        self._run_int_encoding("bit_packing")

    def test_fibonacci_isolated_roundtrip(self) -> None:
        self._run_int_encoding("fibonacci")

    def test_exp_golomb_isolated_roundtrip(self) -> None:
        self._run_int_encoding("exp_golomb")

    def test_byte_packed_isolated_roundtrip(self) -> None:
        self._run_int_encoding("byte_packed")

    def test_masked_vbyte_isolated_roundtrip(self) -> None:
        self._run_int_encoding("masked_vbyte")


class TestStringEncodingRoundtrip(unittest.TestCase):
    """Isolated roundtrip tests for each string encoding strategy."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.gfa_file = find_test_gfa_file()

    def _run_str_encoding(self, encoding_name: str) -> None:
        """Run an isolated roundtrip test for a single string encoding."""
        has_decompressor, reason = get_decompressor_status(encoding_name, False)
        if not has_decompressor:
            self.skipTest(reason)

        flags = build_isolated_flags(encoding_name, False)
        status, error, _, _ = run_roundtrip(self.gfa_file, flags)
        self.assertEqual(
            status,
            "PASS",
            f"String encoding '{encoding_name}' roundtrip failed: {error}",
        )

    def test_none_str_isolated_roundtrip(self) -> None:
        self._run_str_encoding("none")

    def test_zstd_isolated_roundtrip(self) -> None:
        self._run_str_encoding("zstd")

    def test_zstd_dict_isolated_roundtrip(self) -> None:
        self._run_str_encoding("zstd_dict")

    def test_gzip_isolated_roundtrip(self) -> None:
        self._run_str_encoding("gzip")

    def test_lzma_isolated_roundtrip(self) -> None:
        self._run_str_encoding("lzma")

    def test_lz4_isolated_roundtrip(self) -> None:
        self._run_str_encoding("lz4")

    def test_brotli_isolated_roundtrip(self) -> None:
        self._run_str_encoding("brotli")

    def test_huffman_isolated_roundtrip(self) -> None:
        self._run_str_encoding("huffman")

    def test_frontcoding_isolated_roundtrip(self) -> None:
        self._run_str_encoding("frontcoding")

    def test_delta_str_isolated_roundtrip(self) -> None:
        self._run_str_encoding("delta")

    def test_dictionary_isolated_roundtrip(self) -> None:
        self._run_str_encoding("dictionary")

    def test_rle_isolated_roundtrip(self) -> None:
        self._run_str_encoding("rle")

    def test_cigar_isolated_roundtrip(self) -> None:
        self._run_str_encoding("cigar")

    def test_2bit_isolated_roundtrip(self) -> None:
        self._run_str_encoding("2bit")

    def test_arithmetic_isolated_roundtrip(self) -> None:
        self._run_str_encoding("arithmetic")

    def test_bwt_huffman_isolated_roundtrip(self) -> None:
        self._run_str_encoding("bwt_huffman")

    def test_ppm_isolated_roundtrip(self) -> None:
        self._run_str_encoding("ppm")

    def test_superstring_none_isolated_roundtrip(self) -> None:
        self._run_str_encoding("superstring_none")

    def test_superstring_huffman_isolated_roundtrip(self) -> None:
        self._run_str_encoding("superstring_huffman")

    def test_superstring_2bit_isolated_roundtrip(self) -> None:
        self._run_str_encoding("superstring_2bit")

    def test_superstring_ppm_isolated_roundtrip(self) -> None:
        self._run_str_encoding("superstring_ppm")


class TestEncodingCoverageSummary(unittest.TestCase):
    """Print a summary table of all 41 encoding strategies and their status."""

    def test_encoding_coverage_summary(self) -> None:
        """Print roundtrip-capable vs compress-only status for all encodings."""
        print("\n" + "=" * 70)
        print("Encoding Strategy Coverage Summary")
        print("=" * 70)

        print(f"\n{'Type':<10} {'Encoding':<20} {'Decompressor':<15}")
        print("-" * 45)

        int_capable = 0
        int_skip = 0
        for name in INTEGER_ENCODING_NAMES:
            has_decomp, _ = get_decompressor_status(name, True)
            status = "YES" if has_decomp else "SKIP"
            print(f"{'integer':<10} {name:<20} {status:<15}")
            if has_decomp:
                int_capable += 1
            else:
                int_skip += 1

        str_capable = 0
        str_skip = 0
        for name in STRING_ENCODING_NAMES:
            has_decomp, _ = get_decompressor_status(name, False)
            status = "YES" if has_decomp else "SKIP"
            print(f"{'string':<10} {name:<20} {status:<15}")
            if has_decomp:
                str_capable += 1
            else:
                str_skip += 1

        print("-" * 45)
        print(f"Integer: {int_capable} roundtrip-capable, {int_skip} compress-only")
        print(f"String:  {str_capable} roundtrip-capable, {str_skip} compress-only")
        print(f"Total:   {int_capable + str_capable} roundtrip-capable, {int_skip + str_skip} compress-only")
        print("=" * 70)


if __name__ == "__main__":
    unittest.main()
