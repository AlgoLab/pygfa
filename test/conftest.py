import os
from pathlib import Path
import pytest


def pytest_addoption(parser):
    """Add custom command-line options for pytest."""
    parser.addoption(
        "--gfa-file",
        action="store",
        default=None,
        help="Run tests only on the specified GFA file instead of all matching files",
    )


@pytest.fixture(scope="module")
def test_output_dir(request):
    """Provide a dedicated output directory for each test file."""
    # Get test module name without .py extension
    module_name = request.module.__name__
    if module_name.startswith("test_"):
        test_name = module_name[5:]  # Remove "test_" prefix
    else:
        test_name = module_name

    # Create output directory (use absolute path to avoid path resolution issues)
    project_root = Path(__file__).parent.parent  # Go up from test/ to project root
    output_dir = project_root / "results/test" / test_name
    output_dir.mkdir(parents=True, exist_ok=True)

    # Return absolute path to avoid working directory issues
    yield output_dir.resolve()


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Automatically setup test environment for each test."""
    # Tests will use the output directory provided by test_output_dir
    pass


@pytest.fixture
def temp_file_factory(test_output_dir):
    """Factory for creating temporary files in test output directory."""

    def _temp_file(prefix="test", suffix=".tmp"):
        import tempfile

        fd, path = tempfile.mkstemp(prefix=prefix, suffix=suffix, dir=test_output_dir)
        os.close(fd)
        return path

    return _temp_file
