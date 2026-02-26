import os
import datetime
from pathlib import Path
import pytest

# ANSI color codes for terminal output
COLOR_GREEN = "\033[92m"
COLOR_RED = "\033[91m"
COLOR_RESET = "\033[0m"


def pytest_addoption(parser):
    """Add custom command-line options for pytest."""
    parser.addoption(
        "--gfa-file",
        action="store",
        default=None,
        help="Run tests only on the specified GFA file instead of all matching files",
    )


def pytest_runtest_setup(item):
    """Generate exact pytest command without pixi run prefix."""
    if hasattr(item, "function"):
        test_file = item.fspath
        test_name = item.name
        gfa_file = item.config.getoption("--gfa-file")

        # Build command without pixi run
        command = f'python -m pytest {test_file} -k "{test_name}"'
        if gfa_file:
            command += f" --gfa-file {gfa_file}"

        # Store command for later use
        setattr(item, "_test_command", command)


def pytest_runtest_logreport(report):
    """Print command with timestamp and result on same line with color coding."""
    if report.when == "call":
        command = getattr(report.item, "_test_command", None)
        if command:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if report.passed:
                # Green output for passed tests
                print(f"{COLOR_GREEN}[{command}] [{timestamp}] [PASSED]{COLOR_RESET}")
            else:
                # Red output for failed tests with truncated error message
                error_msg = str(report.longreprtext or report.message or "Unknown error")
                # Truncate to 200 characters
                if len(error_msg) > 200:
                    error_msg = error_msg[:197] + "..."
                print(f"{COLOR_RED}[{command}] [{timestamp}] [FAILED] {error_msg}{COLOR_RESET}")


def temp_file_factory(test_output_dir):
    """Factory for creating temporary files in test output directory."""

    def _temp_file(prefix="test", suffix=".tmp"):
        import tempfile

        fd, path = tempfile.mkstemp(prefix=prefix, suffix=suffix, dir=test_output_dir)
        os.close(fd)
        return path

    return _temp_file


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Automatically setup test environment for each test."""
    # Tests will use the output directory provided by test_output_dir
    pass


@pytest.fixture
def pytest_runtest_setup(item):
    """Generate exact pytest command without pixi run prefix."""
    if hasattr(item, "function"):
        test_file = item.fspath
        test_name = item.name
        gfa_file = item.config.getoption("--gfa-file")

        # Build command without pixi run
        command = f'python -m pytest {test_file} -k "{test_name}"'
        if gfa_file:
            command += f" --gfa-file {gfa_file}"

        # Store command for later use
        setattr(item, "_test_command", command)


def pytest_runtest_logreport(report):
    """Print command with timestamp and result on same line with color coding."""
    if report.when == "call":
        command = getattr(report.item, "_test_command", None)
        if command:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if report.passed:
                # Green output for passed tests
                print(f"{COLOR_GREEN}[{command}] [{timestamp}] [PASSED]{COLOR_RESET}")
            else:
                # Red output for failed tests with truncated error message
                error_msg = str(report.longreprtext or report.message or "Unknown error")
                # Truncate to 200 characters
                if len(error_msg) > 200:
                    error_msg = error_msg[:197] + "..."
                print(f"{COLOR_RED}[{command}] [{timestamp}] [FAILED] {error_msg}{COLOR_RESET}")


def temp_file_factory(test_output_dir):
    """Factory for creating temporary files in test output directory."""

    def _temp_file(prefix="test", suffix=".tmp"):
        import tempfile

        fd, path = tempfile.mkstemp(prefix=prefix, suffix=suffix, dir=test_output_dir)
        os.close(fd)
        return path

    return _temp_file
