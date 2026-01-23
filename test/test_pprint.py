import sys

sys.path.insert(0, "../")

import unittest
import os
import tempfile
import subprocess
import pygfa
from pygfa import gfa


class TestPPrint(unittest.TestCase):
    def _test_pprint_output_matches_expected_file(
        self, gfa_filename, expected_filename
    ):
        """Test that pprint output matches expected file content.

        Args:
            gfa_filename: Path to the GFA file to test
            expected_filename: Path to the file containing expected output
        """
        # Create a GFA graph from a file
        graph = gfa.GFA()

        # Read the GFA file
        with open(gfa_filename, "r") as f:
            gfa_content = f.read()

        graph.from_string(gfa_content)

        # Write to a temporary file instead of using StringIO
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".txt"
        ) as temp_file:
            temp_filename = temp_file.name
            original_stdout = sys.stdout
            sys.stdout = temp_file

            try:
                graph.pprint()
            finally:
                sys.stdout = original_stdout

        # Read the temporary file content
        with open(temp_filename, "r") as f:
            pprint_output = f.read()

        # Check if expected file exists, if not create it
        if not os.path.exists(expected_filename):
            # Create the expected file for future comparisons
            with open(expected_filename, "w") as f:
                f.write(pprint_output)

            # For the first run, just check that pprint ran without error
            self.assertTrue(
                True, "Expected file created. Run test again to verify output."
            )
        else:
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

            # Remove temporary file only on success
            os.unlink(temp_filename)

    def test_pprint_output_matches_expected_file(self):
        """Test that pprint output matches expected file content."""
        self._test_pprint_output_matches_expected_file(
            "data/example1.gfa", "data/example1_pprint_expected.txt"
        )


if __name__ == "__main__":
    unittest.main()
