import sys

sys.path.insert(0, "../")

import unittest
import os
from io import StringIO
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
        graph = gfa.GFA()

        # Read the GFA file
        with open(gfa_filename, "r") as f:
            gfa_content = f.read()

        graph.from_string(gfa_content)

        # Capture pprint output
        output = StringIO()
        original_stdout = sys.stdout
        sys.stdout = output

        try:
            graph.pprint()
        finally:
            sys.stdout = original_stdout

        pprint_output = output.getvalue()

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
            # Read expected content
            with open(expected_filename, "r") as f:
                expected_content = f.read()

            # Compare outputs
            self.assertEqual(
                pprint_output,
                expected_content,
                "PPrint output does not match expected file content",
            )

    def test_pprint_output_matches_expected_file(self):
        """Test that pprint output matches expected file content."""
        self._test_pprint_output_matches_expected_file(
            "data/example1.gfa", "data/example1_pprint_expected.txt"
        )


if __name__ == "__main__":
    unittest.main()
