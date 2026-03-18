import os
import glob
import re
import datetime
import pytest

COLOR_GREEN = "\033[92m"
COLOR_RED = "\033[91m"
COLOR_YELLOW = "\033[93m"
COLOR_CYAN = "\033[96m"
COLOR_BOLD = "\033[1m"
COLOR_RESET = "\033[0m"

MEMORY_LIMIT = "8GB"
LARGE_FILE_THRESHOLD = 1 * 1024 * 1024  # 1MB in bytes


def _find_large_gfa_files():
    """Find all GFA files larger than 1MB and their associated test types."""
    large_files = {}
    test_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(test_dir, "..", "data")

    for gfa_file in glob.glob(os.path.join(data_dir, "**/*.gfa"), recursive=True):
        if not os.path.isfile(gfa_file):
            continue
        size = os.path.getsize(gfa_file)
        if size > LARGE_FILE_THRESHOLD:
            test_types = []
            with open(gfa_file) as f:
                for line in f:
                    if not line.startswith("#"):
                        break
                    match = re.match(r"^#\s*test:\s*(\S+)", line)
                    if match:
                        test_types.append(match.group(1))
            if test_types:
                large_files[gfa_file] = {"size": size, "tests": test_types}

    return large_files


LARGE_GFA_FILES = _find_large_gfa_files()

_TEST_TYPES_WITH_LARGE_FILES = set()
for _info in LARGE_GFA_FILES.values():
    _TEST_TYPES_WITH_LARGE_FILES.update(_info["tests"])


_PYTEST_CONFIG = None


def pytest_configure(config):
    """Register the limit_memory marker from pytest-memray."""
    global _PYTEST_CONFIG
    _PYTEST_CONFIG = config
    config.addinivalue_line("markers", "limit_memory: limit memory usage to specified amount (pytest-memray)")


def pytest_collection_modifyitems(config, items):
    """Apply limit_memory marker only to tests that load GFA files > 1MB."""
    for item in items:
        if "limit_memory" in item.keywords:
            continue

        nodeid = item.nodeid
        for test_type in _TEST_TYPES_WITH_LARGE_FILES:
            if test_type in nodeid:
                item.add_marker(pytest.mark.limit_memory(MEMORY_LIMIT))
                break


# Global list to store failed tests
_failed_tests = []


def pytest_addoption(parser):
    """Add custom command-line options for pytest."""
    parser.addoption(
        "--gfa-file",
        action="store",
        default=None,
        help="Run tests only on the specified GFA file instead of all matching files",
    )


def _build_rerun_command(nodeid):
    """Build the full pytest command to rerun a specific test."""
    if _PYTEST_CONFIG is None:
        return f"pixi run python -m pytest {nodeid}"

    args = list(_PYTEST_CONFIG.invocation_params.args)
    # Remove the nodeid if it's already in args (from --lf or similar)
    clean_args = [a for a in args if a != nodeid]

    # Quote args containing spaces or special chars
    quoted = []
    for a in clean_args:
        if " " in a or '"' in a:
            quoted.append(f'"{a}"')
        else:
            quoted.append(a)

    return "pixi run python -m pytest " + " ".join(quoted) + f" {nodeid}"


def _build_other_tests_command(failed_nodeids):
    """Build the command to run all tests except the failed ones."""
    if _PYTEST_CONFIG is None or not failed_nodeids:
        return ""

    args = list(_PYTEST_CONFIG.invocation_params.args)
    # Remove any -x or --maxfail flags (and their values) so we don't stop on first failure
    new_args = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("-x", "--maxfail"):
            # Skip this flag and if it's --maxfail with a value, skip the next one too.
            if arg == "--maxfail":
                i += 1  # skip the value
            i += 1
            continue
        elif arg.startswith("--maxfail="):
            # Skip this entire argument
            i += 1
            continue
        else:
            new_args.append(arg)
            i += 1

    # Add the deselect flags for each failed nodeid
    for nodeid in failed_nodeids:
        new_args.extend(["--deselect", nodeid])

    # Build the command string
    quoted = []
    for a in new_args:
        if " " in a or '"' in a:
            quoted.append(f'"{a}"')
        else:
            quoted.append(a)

    return "pixi run python -m pytest " + " ".join(quoted)


def pytest_runtest_logreport(report):
    """Print command with timestamp and result on same line with color coding."""
    # Also collect failed tests for terminal summary
    if report.when == "call" and report.outcome == "failed":
        _failed_tests.append(report.nodeid)

    if report.when == "call":
        command = _build_rerun_command(report.nodeid)
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


def pytest_sessionfinish(session, exitstatus):
    """Print command to run all tests except the failed ones."""
    pass  # Moved output to pytest_terminal_summary


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Print rerun commands for all failed tests at the very end of output."""
    global _failed_tests

    failed_nodeids = _failed_tests

    if failed_nodeids:
        terminalreporter.section("RERUN COMMANDS FOR FAILED TESTS", sep="=", bold=True, yellow=True)
        for nodeid in failed_nodeids:
            command = _build_rerun_command(nodeid)
            terminalreporter.line(f"  {command}", bold=True, cyan=True)
