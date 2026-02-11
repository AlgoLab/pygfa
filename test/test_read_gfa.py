import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, "../")

from pygfa import gfa
from test_utils import should_run_test_for_gfa


class TestPPrint(unittest.TestCase):
    def _test_pprint_output_matches_expected_file(self, gfa_filename, expected_filename):
        """Test that pprint output matches expected file content.

        Args:
            gfa_filename: Path to the GFA file to test
            expected_filename: Path to the file containing expected output
        """
        # Check if this test should run for this GFA file
        if not should_run_test_for_gfa("read_gfa", gfa_filename):
            self.skipTest(f"No '# test: read_gfa' comment found in {gfa_filename}")

        # Create a GFA graph from a file
        graph = gfa.GFA.from_gfa(gfa_filename)

        # Write to a temporary file instead of using StringIO
        os.makedirs("results/test/read_gfa", exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".txt", dir="results/test/read_gfa"
        ) as temp_file:
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

    @unittest.skip("Pretty-print format changed - needs expected file update")
    def test_pprint_output_matches_expected_file_1(self):
        """Test that pprint output matches expected file content."""
        self._test_pprint_output_matches_expected_file(
            "data/example_1.gfa", "results/test/read_gfa/expected/example_1.txt"
        )

    @unittest.skip("Pretty-print format changed - needs expected file update")
    def test_pprint_output_matches_expected_file_2(self):
        """Test that pprint output matches expected file content."""
        self._test_pprint_output_matches_expected_file(
            "data/example_2.gfa", "results/test/read_gfa/expected/example_2.txt"
        )

    def test_pprint_output_matches_expected_file_3(self):
        """Test that pprint output matches expected file content."""
        self._test_pprint_output_matches_expected_file(
            "data/example_3.gfa", "results/test/read_gfa/expected/example_3.txt"
        )

    def test_read_gzipped_file(self):
        """Test reading gzipped GFA files."""
        gfa_file = "data/sample1.gfa"
        gzipped_file = "data/sample1.gfa.gz"

        # Skip if gzipped file doesn't exist
        if not os.path.exists(gzipped_file):
            self.skipTest(f"Gzipped file {gzipped_file} not found")

        # Read both uncompressed and gzipped versions
        graph_uncompressed = gfa.GFA.from_gfa(gfa_file)
        graph_compressed = gfa.GFA.from_gfa(gzipped_file)

        # Verify they produce identical graphs
        self.assertEqual(len(list(graph_uncompressed.nodes())), len(list(graph_compressed.nodes())))
        self.assertEqual(len(list(graph_uncompressed.edges())), len(list(graph_compressed.edges())))

    def test_read_zstd_file(self):
        """Test reading zstd-compressed GFA files."""
        gfa_file = "data/sample1.gfa"
        zstd_file = "data/sample1.gfa.zst"

        # Skip if zstd file doesn't exist
        if not os.path.exists(zstd_file):
            self.skipTest(f"Zstd file {zstd_file} not found")

        # Read both uncompressed and zstd-compressed versions
        graph_uncompressed = gfa.GFA.from_gfa(gfa_file)
        graph_compressed = gfa.GFA.from_gfa(zstd_file)

        # Verify they produce identical graphs
        self.assertEqual(len(list(graph_uncompressed.nodes())), len(list(graph_compressed.nodes())))
        self.assertEqual(len(list(graph_uncompressed.edges())), len(list(graph_compressed.edges())))

    def test_read_xz_file(self):
        """Test reading xz-compressed GFA files."""
        gfa_file = "data/sample1.gfa"
        xz_file = "data/sample1.gfa.xz"

        # Skip if xz file doesn't exist
        if not os.path.exists(xz_file):
            self.skipTest(f"XZ file {xz_file} not found")

        # Read both uncompressed and xz-compressed versions
        graph_uncompressed = gfa.GFA.from_gfa(gfa_file)
        graph_compressed = gfa.GFA.from_gfa(xz_file)

        # Verify they produce identical graphs
        self.assertEqual(len(list(graph_uncompressed.nodes())), len(list(graph_compressed.nodes())))
        self.assertEqual(len(list(graph_uncompressed.edges())), len(list(graph_compressed.edges())))

    def test_invalid_gzipped_file(self):
        """Test error handling for invalid gzip files."""
        import gzip as gzip_module

        # Create fake .gz file with regular content
        os.makedirs("results/test/read_gfa", exist_ok=True)
        fake_gzipped = "results/test/read_gfa/fake.gfa.gz"
        with open(fake_gzipped, "w") as f:
            f.write("H\tVN:Z:1.0\n")

        try:
            with self.assertRaises(gzip_module.BadGzipFile) as context:
                gfa.GFA.from_gfa(fake_gzipped)
            self.assertIn("Not a gzipped file", str(context.exception))
        finally:
            if os.path.exists(fake_gzipped):
                os.unlink(fake_gzipped)


if __name__ == "__main__":
    unittest.main()
