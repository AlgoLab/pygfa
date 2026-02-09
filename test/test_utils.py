"""Test utilities for parsing GFA test comments.

This module provides utilities for parsing GFA files and extracting
test-related comments.
"""

import os
import re


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


def get_gfa_files_for_test(test_name, data_dir="data"):
    """Get all GFA files in the data directory that have a test comment for this test.

    Args:
        test_name: The name of the test.
        data_dir: Path to the data directory containing GFA files.

    Returns:
        A list of paths to GFA files that have the test comment.
    """
    matching_files = []

    if not os.path.exists(data_dir):
        return matching_files

    for filename in os.listdir(data_dir):
        if filename.endswith(".gfa"):
            gfa_path = os.path.join(data_dir, filename)
            if should_run_test_for_gfa(test_name, gfa_path):
                matching_files.append(gfa_path)

    return matching_files
