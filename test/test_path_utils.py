"""
Test data path utilities for flexible path resolution.

Supports both the current pattern (data/filename.gfa) and
new subdirectory patterns (data/subdir/filename.gfa).
"""

import os


def get_test_data_path(filename, subdirectory=None):
    """
    Get path to test data file, supporting subdirectories.

    Args:
        filename: Test data filename (e.g., "test_biconnected.gfa")
        subdirectory: Optional subdirectory under data/ (e.g., "HLA-zoo")

    Returns:
        Full path to test data file
    """
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

    if subdirectory:
        return os.path.join(repo_root, "data", subdirectory, filename)
    else:
        return os.path.join(repo_root, "data", filename)


def get_repo_root():
    """
    Get the repository root directory.
    """
    return os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


# Backward compatibility - maintain existing pattern
def get_test_data_path_legacy(filename):
    """
    Legacy function for backward compatibility.
    Uses the original pattern: data/filename.gfa
    """
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", filename)
