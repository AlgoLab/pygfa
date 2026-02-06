import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, "../")

import pygfa
from pygfa import gfa


class TestPPrint(unittest.TestCase):
    def _test_pprint_output_matches_expected_file(self, gfa_filename, expected_filename):
        """Test that pprint output matches expected file content.

        Args:
            gfa_filename: Path to the GFA file to test
            expected_filename: Path to the file containing expected output
        """
        # Create a GFA graph from a file
        graph = gfa.GFA.from_gfa(gfa_filename)

        # Write to a temporary file instead of using StringIO
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as temp_file:
            temp_filename = temp_file.name
            original_stdout = sys.stdout
            sys.stdout = temp_file

            try:
                graph.pprint()
            finally:
                sys.stdout = original_stdout

        if not os.path.exists(expected_filename):
            shutil.copy(temp_filename, expected_filename)
        # Use the standard diff program to look for differences
        result = subprocess.run(
            ["diff", "-u", expected_filename, temp_filename],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            # Differences found
            self.fail(
                f"PPrint output does not match expected file content.\n"
                f"Expected file: {expected_filename}\n"
                f"Actual file: {temp_filename}\n"
                f"Differences:\n{result.stdout}"
            )
        else:
            # Remove temporary file only on success
            os.unlink(temp_filename)

    def test_pprint_output_matches_expected_file_1(self):
        """Test that pprint output matches expected file content."""
        self._test_pprint_output_matches_expected_file(
            "data/example_1.gfa", "results/example_1.txt"
        )

    def test_pprint_output_matches_expected_file_2(self):
        """Test that pprint output matches expected file content."""
        self._test_pprint_output_matches_expected_file(
            "data/example_2.gfa", "results/example_2.txt"
        )

    def test_pprint_output_matches_expected_file_3(self):
        """Test that pprint output matches expected file content."""
        self._test_pprint_output_matches_expected_file(
            "data/example_3.gfa", "results/example_3.txt"
        )


if __name__ == "__main__":
    unittest.main()
