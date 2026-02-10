"""Centralized output directory management for pygfa.

This module provides utilities to ensure consistent output directory
structure across tests and benchmarks.
"""

import os
import tempfile
from pathlib import Path
from typing import Optional


class OutputManager:
    """Manages output directories for tests and benchmarks.

    Ensures all output goes to appropriate subdirectories under results/
    and provides cleanup utilities.
    """

    def __init__(self, base_dir: str = "results"):
        """Initialize output manager.

        Args:
            base_dir: Base directory for all outputs (default: "results")
        """
        self.base_dir = Path(base_dir)

    def get_test_dir(self, test_name: str) -> Path:
        """Get test-specific output directory.

        Args:
            test_name: Name of the test

        Returns:
            Path to test output directory
        """
        return self.base_dir / "test" / test_name

    def get_benchmark_dir(self) -> Path:
        """Get benchmark output directory.

        Returns:
            Path to benchmark output directory
        """
        return self.base_dir / "benchmark"

    def ensure_dir(self, path: Path) -> Path:
        """Ensure directory exists and return path.

        Args:
            path: Directory path to ensure

        Returns:
            Path to ensured directory
        """
        path.mkdir(parents=True, exist_ok=True)
        return path

    def clean_temp_files(self, pattern: str = "tmp*", directory: Optional[Path] = None) -> None:
        """Clean temporary files matching pattern.

        Args:
            pattern: Glob pattern for files to clean
            directory: Directory to clean (default: system temp dir)
        """
        if directory is None:
            directory = Path(tempfile.gettempdir())

        for temp_file in directory.glob(pattern):
            try:
                temp_file.unlink()
            except (FileNotFoundError, PermissionError):
                pass

    def create_temp_file(self, suffix: str, directory: Optional[Path] = None) -> Path:
        """Create temporary file in appropriate directory.

        Args:
            suffix: File suffix
            directory: Directory for temp file (default: system temp dir)

        Returns:
            Path to created temporary file
        """
        if directory is None:
            directory = Path(tempfile.gettempdir())

        fd, path = tempfile.mkstemp(suffix=suffix, dir=str(directory))
        os.close(fd)
        return Path(path)
