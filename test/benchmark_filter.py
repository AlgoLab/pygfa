#!/usr/bin/env python3
"""
Benchmark GFA file filter for pygfa benchmark system.

This module provides utilities to filter GFA files based on benchmark comments.
Benchmark comments must be at the beginning of GFA files and follow the pattern:
  # benchmark: NAME

Where NAME is the name of the benchmark. If NAME is missing, the GFA file must
be used for all benchmarks. Only other comments may precede benchmark comments.

Single-Parameter Benchmarks:
  # benchmark: single_param      - Include in all single-param benchmarks
  # benchmark: int_encoding      - Integer encoding benchmark
  # benchmark: str_encoding      - String encoding benchmark
  # benchmark: block_size        - Block size benchmark
  # benchmark: block_specific    - Block-specific compression benchmark

Section-Specific Benchmarks:
  Test encoding methods for individual sections:
  # benchmark: segment_names_header
  # benchmark: segment_names_payload_lengths
  # benchmark: segment_names_payload_names
  # benchmark: segments_header
  # benchmark: segments_payload_lengths
  # benchmark: segments_payload_strings
  # benchmark: links_header
  # benchmark: links_payload_from
  # benchmark: links_payload_to
  # benchmark: links_payload_cigar_lengths
  # benchmark: links_payload_cigar
  # benchmark: paths_header
  # benchmark: paths_payload_names
  # benchmark: paths_payload_segment_lengths
  # benchmark: paths_payload_path_ids
  # benchmark: paths_payload_cigar_lengths
  # benchmark: paths_payload_cigar
  # benchmark: walks_header
  # benchmark: walks_payload_sample_ids
  # benchmark: walks_payload_hep_indices
  # benchmark: walks_payload_sequence_ids
  # benchmark: walks_payload_start
  # benchmark: walks_payload_end
  # benchmark: walks_payload_walks
"""

import os
import argparse
from typing import List, Dict, Optional
import sys
import re


def extract_header_comments(gfa_path: str) -> List[str]:
    """
    Extract all comments from the beginning of a GFA file.

    Stops reading at the first non-comment line (line not starting with '#').

    Args:
        gfa_path: Path to GFA file

    Returns:
        List of comment lines (including '#')
    """
    comments = []
    try:
        # Handle gzipped files
        if gfa_path.endswith(".gz"):
            import gzip

            open_func = gzip.open
        else:
            open_func = open

        with open_func(gfa_path, "rt", encoding="utf-8") as f:
            for line in f:
                stripped_line = line.strip()
                if stripped_line.startswith("#"):
                    comments.append(stripped_line)
                else:
                    # Stop at first non-comment line
                    break
    except UnicodeDecodeError:
        # Try different encoding for gzipped files
        try:
            if gfa_path.endswith(".gz"):
                import gzip

                with gzip.open(gfa_path, "rt", encoding="latin-1") as f:
                    for line in f:
                        stripped_line = line.strip()
                        if stripped_line.startswith("#"):
                            comments.append(stripped_line)
                        else:
                            break
        except Exception as e:
            print(f"Warning: Could not decode file {gfa_path}: {e}", file=sys.stderr)
    except (OSError, IOError) as e:
        print(f"Warning: Could not read file {gfa_path}: {e}", file=sys.stderr)

    return comments


def filter_gfa_files(data_dir: str, benchmark_name: Optional[str] = None) -> List[str]:
    """
    Filter GFA files based on benchmark comments.

    Args:
        data_dir: Directory containing GFA files (scans recursively)
        benchmark_name: If None, return all files with any '# benchmark:' comment.
                       If specified, return files with '# benchmark: NAME'.
                       If empty string, return files with unnamed '# benchmark:'.

    Returns:
        List of GFA file paths matching the criteria
    """
    # Find all GFA files recursively
    gfa_files = []
    for root, _, files in os.walk(data_dir):
        for file in files:
            if file.endswith(".gfa") or file.endswith(".gfa.gz"):
                gfa_files.append(os.path.join(root, file))

    matching_files = []

    for gfa_file in gfa_files:
        comments = extract_header_comments(gfa_file)
        benchmark_comments = [c for c in comments if re.match(r"^#\s*benchmark:", c)]

        if not benchmark_comments:
            continue

        if benchmark_name is None:
            # Return all files with any benchmark comment
            matching_files.append(gfa_file)
        else:
            # Check for specific benchmark name
            for comment in benchmark_comments:
                # Remove '# benchmark:' prefix and strip whitespace
                comment_content = comment[len("# benchmark:") :].strip()

                if benchmark_name == "":
                    # Looking for unnamed benchmark
                    if comment_content == "":
                        matching_files.append(gfa_file)
                        break
                else:
                    # Looking for specific benchmark name
                    if comment_content == benchmark_name:
                        matching_files.append(gfa_file)
                        break

    return sorted(matching_files)


def generate_dataset_config(
    data_dir: str, benchmark_name: Optional[str] = None
) -> Dict[str, str]:
    """
    Generate Snakemake dataset configuration from filtered GFA files.

    Args:
        data_dir: Directory containing GFA files
        benchmark_name: Benchmark name filter (same as filter_gfa_files)

    Returns:
        Dictionary mapping dataset names to file paths
    """
    files = filter_gfa_files(data_dir, benchmark_name)

    datasets = {}
    for file_path in files:
        # Create dataset name from filename
        # Remove extension and path components
        filename = os.path.basename(file_path)
        dataset_name = filename

        # Remove .gfa or .gfa.gz extension
        if dataset_name.endswith(".gfa.gz"):
            dataset_name = dataset_name[:-7]
        elif dataset_name.endswith(".gfa"):
            dataset_name = dataset_name[:-4]

        # Handle duplicate names by adding parent directory
        if dataset_name in datasets:
            # Try to make unique by adding parent directory
            parent_dir = os.path.basename(os.path.dirname(file_path))
            dataset_name = f"{parent_dir}_{dataset_name}"

            # If still duplicate, use full relative path
            if dataset_name in datasets:
                rel_path = os.path.relpath(file_path, data_dir)
                dataset_name = rel_path.replace("/", "_").replace(".", "_")

        datasets[dataset_name] = file_path

    return datasets


def format_dataset_config(datasets: Dict[str, str]) -> str:
    """
    Format dataset configuration as Python dictionary for Snakemake.

    Args:
        datasets: Dictionary mapping dataset names to file paths

    Returns:
        Formatted Python dictionary string
    """
    if not datasets:
        return "{}"

    lines = []
    for name, path in sorted(datasets.items()):
        lines.append(f'    "{name}": "{path}"')

    return "{\n" + ",\n".join(lines) + "\n}"


def main():
    parser = argparse.ArgumentParser(
        description="Filter GFA files based on benchmark comments",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --data-dir data --list
  %(prog)s --data-dir data --benchmark-name "compression"
  %(prog)s --data-dir data --config --benchmark-name "roundtrip"
        """,
    )

    parser.add_argument(
        "--data-dir",
        "-d",
        default="data",
        help="Directory containing GFA files (default: data)",
    )

    parser.add_argument(
        "--benchmark-name",
        "-n",
        default=None,
        help="Filter by benchmark name. If omitted, list all benchmark files.",
    )

    parser.add_argument(
        "--list", "-l", action="store_true", help="List matching GFA file paths"
    )

    parser.add_argument(
        "--config",
        "-c",
        action="store_true",
        help="Generate Snakemake configuration dictionary",
    )

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show detailed information"
    )

    args = parser.parse_args()

    if not os.path.isdir(args.data_dir):
        print(
            f"Error: Data directory '{args.data_dir}' does not exist", file=sys.stderr
        )
        sys.exit(1)

    # Handle empty string for unnamed benchmarks
    if args.benchmark_name == "":
        benchmark_filter = ""
    else:
        benchmark_filter = args.benchmark_name

    files = filter_gfa_files(args.data_dir, benchmark_filter)

    if not files:
        print("No GFA files found with benchmark comment", end="")
        if benchmark_filter is not None:
            print(f" matching '{benchmark_filter}'", end="")
        print(".")
        sys.exit(0)

    if args.list:
        for file_path in files:
            print(file_path)

    elif args.config:
        datasets = generate_dataset_config(args.data_dir, benchmark_filter)
        print(format_dataset_config(datasets))

    else:
        # Default: show summary
        print(f"Found {len(files)} GFA files", end="")
        if benchmark_filter is not None:
            print(f" for benchmark '{benchmark_filter}'", end="")
        print(":")
        for file_path in files:
            rel_path = os.path.relpath(file_path, args.data_dir)
            print(f"  - {rel_path}")

            if args.verbose:
                comments = extract_header_comments(file_path)
                benchmark_comments = [
                    c for c in comments if c.strip().startswith("# benchmark:")
                ]
                for comment in benchmark_comments:
                    print(f"    {comment}")


if __name__ == "__main__":
    main()
