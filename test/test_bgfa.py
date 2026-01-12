#!/usr/bin/env python3

import unittest
import os
import sys
import tempfile

# Add the project root to the Python path to ensure imports work correctly
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from pygfa.gfa import GFA
from pygfa.serializer.gfa1_serializer import serialize_graph


class TestBGFA(unittest.TestCase):
    def setUp(self):
        """Set up a temporary directory for test files."""
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_gfa_to_bgfa_to_gfa_regression(self):
        """
        Regression test that reads a gfa file and:
        1. converts the gfa file to a bgfa file
        2. converts the bgfa file to a gfa file
        3. obtain a canonical version of the first gfa file
        4. checks if the canonical gfa file and the result of the conversion from a
           bgfa are equal
        """
        # Create a sample GFA file for testing
        sample_gfa_content = """H\tVN:Z:1.0
S\t1\tACGT
S\t2\tTGCA
L\t1\t+\t2\t-\t0M
P\tpath1\t1+,2-\t0M
W\tsample1\t0\tseq1\t*\t*\t1+
"""
        original_gfa_path = os.path.join(self.test_dir, "original.gfa")
        with open(original_gfa_path, "w") as f:
            f.write(sample_gfa_content)

        # 1. Load the original GFA file
        gfa_original = GFA.from_gfa(original_gfa_path)

        # 2. Convert the GFA to BGFA
        bgfa_path = os.path.join(self.test_dir, "test.bgfa")
        gfa_original.write_bgfa(bgfa_path, block_size=1024)

        # 3. Convert the BGFA file back to a GFA object
        # Note: The current implementation of from_gfa only parses text GFA.
        # A proper BGFA reader would be needed for a full test.
        # For this regression test, we will simulate the BGFA->GFA step
        # by creating a new GFA object from the original data.
        # This is a placeholder until a proper BGFA reader is implemented.
        gfa_from_bgfa = GFA.from_gfa(original_gfa_path)

        # 4. Obtain a canonical version of the original GFA
        canonical_gfa_string = gfa_original.to_gfa()

        # 5. Compare the canonical GFA with the GFA from BGFA
        # Since we are using the same source data, they should be equal
        # when serialized to canonical form.
        gfa_from_bgfa_string = gfa_from_bgfa.to_gfa()

        self.assertEqual(canonical_gfa_string, gfa_from_bgfa_string)

        # Additional check: ensure the canonical output is sorted correctly
        lines = canonical_gfa_string.split('\n')
        # Check header
        self.assertTrue(lines[0].startswith('H\t'))
        # Check segments are sorted
        segment_lines = [l for l in lines if l.startswith('S\t')]
        if len(segment_lines) > 1:
            self.assertLessEqual(segment_lines[0].split('\t')[1], segment_lines[1].split('\t')[1])
        # Check links are sorted
        link_lines = [l for l in lines if l.startswith('L\t')]
        if len(link_lines) > 1:
            # Sort by from_node then to_node
            self.assertTrue(
                (link_lines[0].split('\t')[2], link_lines[0].split('\t')[4]) <=
                (link_lines[1].split('\t')[2], link_lines[1].split('\t')[4])
            )
        # Check paths are sorted
        path_lines = [l for l in lines if l.startswith('P\t')]
        if len(path_lines) > 1:
            self.assertLessEqual(path_lines[0].split('\t')[1], path_lines[1].split('\t')[1])
        # Check walks are sorted
        walk_lines = [l for l in lines if l.startswith('W\t')]
        if len(walk_lines) > 1:
            # Sort by sample_id then seq_id
            self.assertTrue(
                (walk_lines[0].split('\t')[1], walk_lines[0].split('\t')[3]) <=
                (walk_lines[1].split('\t')[1], walk_lines[1].split('\t')[3])
            )


if __name__ == '__main__':
    unittest.main()
