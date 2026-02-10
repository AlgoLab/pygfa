import os
from pathlib import Path
import pytest


@pytest.fixture(scope="module")
def test_output_dir(request):
    """Provide a dedicated output directory for each test file."""
    # Get test module name without .py extension
    module_name = request.module.__name__
    if module_name.startswith("test_"):
        test_name = module_name[5:]  # Remove "test_" prefix
    else:
        test_name = module_name

    # Create output directory
    output_dir = Path("results/test") / test_name
    output_dir.mkdir(parents=True, exist_ok=True)

    # Change to module's output directory for duration of test
    original_cwd = os.getcwd()
    os.chdir(output_dir)

    yield output_dir

    # Restore original working directory
    os.chdir(original_cwd)


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
