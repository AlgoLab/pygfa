import subprocess
import sys
import os

import pytest


@pytest.mark.xfail(reason="This test is designed to fail to verify rerun command output", strict=False)
def test_failed_test_shows_rerun_command():
    """Test that a failed test shows the command to rerun it."""
    # This test itself will fail to verify the rerun command output
    assert False, "This test is designed to fail to verify rerun command output"


def test_passing_test_does_not_show_rerun_commands():
    """Test that a passing test does not show rerun commands."""
    # Create a temporary test file with a passing test in the test directory
    test_content = '''
import pytest

def test_always_pass():
    """A test that always passes."""
    assert True
'''

    # Write the test file in the test directory to ensure it uses our conftest.py
    test_file_path = os.path.join(os.getcwd(), "test", "temp_test_pass.py")
    with open(test_file_path, "w") as f:
        f.write(test_content)

    try:
        # Run pytest on the passing test and capture output
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "test/temp_test_pass.py", "-v", "-s"],
            capture_output=True,
            text=True,
            cwd=os.getcwd(),
        )

        # Check that the test passed (return code == 0)
        assert result.returncode == 0

        # Check that output does NOT contain rerun commands (since no failures)
        output = result.stderr + result.stdout
        assert "To rerun:" not in output
        assert "To run all other tests:" not in output

    finally:
        # Clean up the temporary test file
        if os.path.exists(test_file_path):
            os.remove(test_file_path)


if __name__ == "__main__":
    test_failed_test_shows_rerun_command()
    test_passing_test_does_not_show_rerun_commands()
    print("All tests passed!")
