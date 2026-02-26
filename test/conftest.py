import os
import datetime
import pytest

# ANSI color codes for terminal output
COLOR_GREEN = "\033[92m"
COLOR_RED = "\033[91m"
COLOR_YELLOW = "\033[93m"
COLOR_RESET = "\033[0m"


def pytest_addoption(parser):
    """Add custom command-line options for pytest."""
    parser.addoption(
        "--gfa-file",
        action="store",
        default=None,
        help="Run tests only on the specified GFA file instead of all matching files",
    )


def pytest_runtest_logreport(report):
    """Print command with timestamp and result on same line with color coding."""
    if report.when == "call":
        command = f"python -m pytest {report.nodeid}"
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if report.passed:
            print(f"{COLOR_GREEN}[{command}] [{timestamp}] [PASSED]{COLOR_RESET}")
        elif report.skipped:
            print(f"{COLOR_YELLOW}[{command}] [{timestamp}] [SKIPPED]{COLOR_RESET}")
        else:
            error_msg = str(report.longreprtext or report.message or "Unknown error")
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
    pass


@pytest.fixture
def test_output_dir(tmp_path):
    """Provide a temporary directory for test outputs."""
    return tmp_path
