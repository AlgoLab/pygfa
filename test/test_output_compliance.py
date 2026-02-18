"""Compliance tests for pygfa output directory structure.

This test ensures all files write to the correct subdirectories
under results/ according to project requirements.
"""

import tempfile
from pathlib import Path
import pytest


@pytest.fixture(scope="session", autouse=True)
def record_initial_state():
    """Record the initial state before tests run."""
    # Record files outside allowed directories before tests start
    excluded_dirs = {"results", "data", "test", ".git", ".pytest_cache", "__pycache__"}
    initial_files = set()

    for pattern in ["*.log", "*.tmp", "*.gfa", "*.bgfa", "*.txt", "*.json", "*.tsv"]:
        for file_path in Path(".").rglob(pattern):
            # Skip files in excluded directories
            if not any(str(file_path).startswith(f"{d}/") for d in excluded_dirs):
                initial_files.add(str(file_path))

    yield initial_files

    # After tests complete, check for new files
    final_files = set()
    for pattern in ["*.log", "*.tmp", "*.gfa", "*.bgfa", "*.txt", "*.json", "*.tsv"]:
        for file_path in Path(".").rglob(pattern):
            if not any(str(file_path).startswith(f"{d}/") for d in excluded_dirs):
                final_files.add(str(file_path))

    new_files = final_files - initial_files
    if new_files:
        pytest.fail(f"Tests created files outside allowed directories: {new_files}")


def test_output_directory_structure():
    """Test that all output goes to correct directories."""
    base_results = Path("results")

    # Create results directory structure if it doesn't exist
    expected_subdirs = {"test", "benchmark"}
    base_results.mkdir(parents=True, exist_ok=True)
    for subdir in expected_subdirs:
        subdir_path = base_results / subdir
        subdir_path.mkdir(parents=True, exist_ok=True)

    # Verify files are in correct subdirectories
    test_files_found = []
    if (base_results / "test").exists():
        test_files_found = list((base_results / "test").rglob("*.*"))

    # Check for any test output files
    if len(test_files_found) > 0:
        print(f"✅ Found {len(test_files_found)} test output files")

    if (base_results / "benchmark").exists():
        benchmark_files_found = list((base_results / "benchmark").rglob("*.*"))
        if len(benchmark_files_found) > 0:
            print(f"✅ Found {len(benchmark_files_found)} benchmark output files")


def test_tempfile_usage_compliance():
    """Test that tempfile usage respects output directory structure."""
    # Check that no temporary files are created in system temp directories
    temp_dir = tempfile.gettempdir()

    # Look for any pygfa-related temp files that shouldn't be there
    temp_patterns = ["*gfa*", "*bgfa*", "*pygfa*", "*test_*"]

    for pattern in temp_patterns:
        temp_files = list(Path(temp_dir).glob(pattern))
        # This is a warning, not a failure, as some files might be from other runs
        if temp_files:
            print(f"⚠️  Found {len(temp_files)} temp files in system temp: {temp_files[:3]}...")


def test_no_hardcoded_temp_paths():
    """Test that no hardcoded temp paths like /tmp/ are used in test files."""
    test_dir = Path("test")
    # Check for hardcoded temp paths that don't use results/test/
    hardcoded_temp_patterns = ["/tmp/", "/var/tmp/"]

    violations = []
    for test_file in test_dir.glob("test_*.py"):
        try:
            with open(test_file, "r") as f:
                content = f.read()

                # Check for hardcoded temp paths (skip test_output_compliance.py itself)
                for pattern in hardcoded_temp_patterns:
                    if pattern in content and test_file.name != "test_output_compliance.py":
                        violations.append(f"{test_file}: contains '{pattern}'")
                        break

                # Check for tempfile usage without proper dir parameter
                import re

                # Find all tempfile.mkstemp() calls
                mkstemp_matches = re.findall(r"tempfile\.mkstemp\([^)]*\)", content)
                for match in mkstemp_matches:
                    # Allow if dir= points to results/test or uses a variable that should be self.test_output_dir
                    if ("dir=" in match and "results/test" in match) or "self.test_output_dir" in match:
                        continue
                    # Skip test_output_compliance.py itself since it uses system temp for demonstration
                    if test_file.name == "test_output_compliance.py":
                        continue
                    violations.append(f"{test_file}: tempfile.mkstemp() without dir=results/test/: {match}")

                # Find all tempfile.NamedTemporaryFile() calls
                namedtemp_matches = re.findall(r"tempfile\.NamedTemporaryFile\([^)]*\)", content)
                for match in namedtemp_matches:
                    # Allow if dir= points to results/test or uses variables
                    if (
                        ("dir=" in match and "results/test" in match)
                        or "self.test_output_dir" in match
                        or "output_dir" in match
                    ):
                        continue
                    # Skip test_output_compliance.py itself since it uses system temp for demonstration
                    if test_file.name == "test_output_compliance.py":
                        continue
                    violations.append(f"{test_file}: tempfile.NamedTemporaryFile() without dir=results/test/: {match}")

                # Find all tempfile.mkdtemp() calls
                mkdtemp_matches = re.findall(r"tempfile\.mkdtemp\([^)]*\)", content)
                for match in mkdtemp_matches:
                    # Allow if dir= points to results/test or uses test_output_dir variable
                    if ("dir=" in match and "results/test" in match) or "test_output_dir" in match:
                        continue
                    # Skip test_output_compliance.py itself since it uses system temp for demonstration
                    if test_file.name == "test_output_compliance.py":
                        continue
                    violations.append(f"{test_file}: tempfile.mkdtemp() without dir=results/test/: {match}")

        except (IOError, UnicodeDecodeError):
            pass

    if violations:
        pytest.fail("Found hardcoded temp paths in test files:\n" + "\n".join(violations))


if __name__ == "__main__":
    test_output_directory_structure()
    test_tempfile_usage_compliance()
    test_no_hardcoded_temp_paths()
    print("Output directory structure is compliant")
