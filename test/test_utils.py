"""Test utilities for parsing GFA test comments.

This module provides utilities for parsing GFA files and extracting
test-related comments.
"""

import os
import re
import sys


def get_test_names_from_gfa(gfa_path):
    """Parse a GFA file and extract test names from comments.

    Each GFA file can have one or more comments of the form `# test: TESTNAME`
    at the beginning of the file. The comment `# test: TESTNAME` means that
    the GFA file must be used as a test case of the test file named
    `test_TESTNAME.py` or `TESTNAME.py` in the test directory.

    Args:
        gfa_path: Path to the GFA file.

    Returns:
        A list of test names extracted from the GFA file comments.
        Returns an empty list if no test comments are found.
    """
    test_names = []

    # Get the absolute path if relative
    if not os.path.isabs(gfa_path):
        # Get the directory of the calling test file
        gfa_path = os.path.abspath(gfa_path)

    if not os.path.exists(gfa_path):
        return test_names

    with open(gfa_path, "r") as f:
        for line in f:
            line = line.strip()
            # Stop at first non-comment line
            if not line.startswith("#"):
                break
            # Parse test comment
            match = re.match(r"^#\s*test:\s*(\S+)", line)
            if match:
                test_names.append(match.group(1))

    return test_names


def should_run_test_for_gfa(test_name, gfa_path):
    """Check if a test should run for a given GFA file.

    A test should only run if there is a corresponding `# test: TESTNAME`
    comment in the GFA file.

    Args:
        test_name: The name of the test (e.g., 'read_gfa' or 'compression').
        gfa_path: Path to the GFA file.

    Returns:
        True if the test should run for this GFA file, False otherwise.
    """
    # Normalize test name (remove 'test_' prefix if present)
    normalized_test_name = test_name
    if normalized_test_name.startswith("test_"):
        normalized_test_name = normalized_test_name[5:]

    test_names = get_test_names_from_gfa(gfa_path)

    # Check if the test name matches any of the test comments
    for gfa_test_name in test_names:
        if gfa_test_name == normalized_test_name:
            return True
        # Also check with 'test_' prefix
        if gfa_test_name == test_name:
            return True

    return False


def get_test_data_path(filename, data_dir="data"):
    """Get path to a test data file.

    Args:
        filename: Name of the file in the data directory.
        data_dir: Path to the data directory (default: "data").

    Returns:
        Full path to the test data file.
    """
    return os.path.join(data_dir, filename)


def get_gfa_files_for_test(test_name, data_dir=None):
    """Get all GFA files in the data directory that have a test comment for this test.

    Args:
        test_name: The name of the test.
        data_dir: Path to the data directory containing GFA files.
                  If None, defaults to 'data' directory relative to the test directory.

    Returns:
        A list of paths to GFA files that have the test comment.
    """
    matching_files = []

    # Determine default data directory
    if data_dir is None:
        # Get the test directory (where test_utils.py is located)
        test_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(test_dir, "..", "data")
        data_dir = os.path.normpath(data_dir)

    if not os.path.exists(data_dir):
        return matching_files

    for filename in os.listdir(data_dir):
        if filename.endswith(".gfa"):
            gfa_path = os.path.join(data_dir, filename)
            if should_run_test_for_gfa(test_name, gfa_path):
                matching_files.append(gfa_path)

    return matching_files


def get_gfa_file_from_args(test_name, data_dir=None):
    """Get GFA file from command-line args, environment variable, or auto-discover.

    Usage:
        python test_testname.py [gfa_file]
        GFA_FILE=data/test_compression.gfa python test_testname.py

    If a GFA file path is provided as:
    1. The GFA_FILE environment variable, OR
    2. The second element of sys.argv (sys.argv[1]) - only if it looks like a valid file path

    Then it validates that the file has the appropriate '# test: TESTNAME' comment
    and returns that file.

    Otherwise, auto-discovers all GFA files in data_dir with matching test comment.
    Returns the first match, or raises ValueError if no matching files found.

    Note: When running with unittest directly (not pytest), arguments after the script name
    are interpreted as test selectors. Use GFA_FILE environment variable or pytest --gfa-file
    option to avoid conflicts.

    Args:
        test_name: The name of the test (e.g., 'compression', 'gfa_operations').
        data_dir: Path to the data directory. If None, uses 'data' relative to test directory.

    Returns:
        Path to the GFA file to test.

    Raises:
        ValueError: If no matching GFA file is found.
    """
    gfa_path = None

    # First, check GFA_FILE environment variable
    gfa_path = os.environ.get("GFA_FILE")

    if gfa_path:
        # Make path absolute if relative
        if not os.path.isabs(gfa_path):
            gfa_path = os.path.abspath(gfa_path)

        if not os.path.exists(gfa_path):
            raise ValueError(f"GFA file not found: {gfa_path}")

        # Validate that this file has the correct test comment
        if not should_run_test_for_gfa(test_name, gfa_path):
            raise ValueError(
                f"GFA file '{gfa_path}' does not have '# test: {test_name}' comment. "
                f"Use a file with the appropriate test comment or run without arguments "
                f"to auto-discover matching files."
            )

        return gfa_path

    # Check if a GFA file was provided as command-line argument
    # Only if it looks like a valid file path (exists and ends with .gfa)
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        # Skip unittest arguments (those starting with -)
        if arg.startswith("-"):
            arg = None
        # Only accept if it's a valid .gfa file that exists
        elif not (arg.endswith(".gfa") and os.path.exists(arg)):
            arg = None

        if arg:
            gfa_path = arg
            # Make path absolute if relative
            if not os.path.isabs(gfa_path):
                gfa_path = os.path.abspath(gfa_path)

            if not os.path.exists(gfa_path):
                raise ValueError(f"GFA file not found: {gfa_path}")

            # Validate that this file has the correct test comment
            if not should_run_test_for_gfa(test_name, gfa_path):
                raise ValueError(
                    f"GFA file '{gfa_path}' does not have '# test: {test_name}' comment. "
                    f"Use a file with the appropriate test comment or run without arguments "
                    f"to auto-discover matching files."
                )

            return gfa_path

    # Auto-discover matching files
    matching_files = get_gfa_files_for_test(test_name, data_dir)

    if not matching_files:
        # Determine data_dir for error message
        if data_dir is None:
            test_dir = os.path.dirname(os.path.abspath(__file__))
            data_dir = os.path.join(test_dir, "..", "data")
            data_dir = os.path.normpath(data_dir)
        raise ValueError(
            f"No GFA files found with '# test: {test_name}' comment in '{data_dir}'. "
            f"Provide a GFA file path as argument or set GFA_FILE environment variable."
        )

    return matching_files[0]


def get_benchmark_names_from_gfa(gfa_path):
    """Parse a GFA file and extract benchmark names from comments.

    Each GFA file can have one or more comments of the form `# benchmark: NAME`
    at the beginning of the file. The comment `# benchmark: NAME` means that
    the GFA file must be used for the benchmark named NAME.

    Args:
        gfa_path: Path to the GFA file.

    Returns:
        A list of benchmark names extracted from the GFA file comments.
        Returns an empty list if no benchmark comments are found.
    """
    benchmark_names = []

    if not os.path.isabs(gfa_path):
        gfa_path = os.path.abspath(gfa_path)

    if not os.path.exists(gfa_path):
        return benchmark_names

    with open(gfa_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line.startswith("#"):
                break
            match = re.match(r"^#\s*benchmark:\s*(\S+)", line)
            if match:
                benchmark_names.append(match.group(1))

    return benchmark_names


def should_run_benchmark_for_gfa(benchmark_name, gfa_path):
    """Check if a benchmark should run for a given GFA file.

    A benchmark should only run if there is a corresponding `# benchmark: NAME`
    comment in the GFA file.

    Args:
        benchmark_name: The name of the benchmark (e.g., 'roundtrip_small').
        gfa_path: Path to the GFA file.

    Returns:
        True if the benchmark should run for this GFA file, False otherwise.
    """
    benchmark_names = get_benchmark_names_from_gfa(gfa_path)
    return benchmark_name in benchmark_names


def get_all_gfa_files_for_test(test_name, data_dir="data"):
    """Get all GFA files for a test, optionally filtered by command-line argument.

    Usage: python test_testname.py [gfa_file]

    If a GFA file path is provided as sys.argv[1], returns only that file (if valid).
    Otherwise, returns all GFA files in data_dir with matching test comment.

    Args:
        test_name: The name of the test (e.g., 'compression', 'gfa_operations').
        data_dir: Path to the data directory (default: "data").

    Returns:
        List of paths to GFA files to test.

    Raises:
        ValueError: If sys.argv[1] is provided but is invalid.
    """
    # Check if a specific GFA file was provided as command-line argument
    if len(sys.argv) > 1:
        gfa_path = sys.argv[1]
        # Make path absolute if relative
        if not os.path.isabs(gfa_path):
            gfa_path = os.path.abspath(gfa_path)

        if not os.path.exists(gfa_path):
            raise ValueError(f"GFA file not found: {gfa_path}")

        # Validate that this file has the correct test comment
        if not should_run_test_for_gfa(test_name, gfa_path):
            raise ValueError(
                f"GFA file '{gfa_path}' does not have '# test: {test_name}' comment. "
                f"Use a file with the appropriate test comment or run without arguments "
                f"to auto-discover matching files."
            )

        return [gfa_path]

    # Auto-discover all matching files
    matching_files = get_gfa_files_for_test(test_name, data_dir)

    if not matching_files:
        raise ValueError(
            f"No GFA files found with '# test: {test_name}' comment in '{data_dir}'. "
            f"Provide a GFA file path as argument."
        )

    return matching_files
