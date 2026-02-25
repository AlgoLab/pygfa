import logging
import sys
import unittest

sys.path.insert(0, "../")

import pygfa
from test_utils import should_run_test_for_gfa, get_gfa_file_from_args

logging.basicConfig(level=logging.DEBUG)

#                                                             ___________
#                                                            |           |
#   ___________      [14_14_14]                             [5_5_5]     [8_8_8]
#  |           |      |                                     /
# [10_10_10]  [11_11_11]                                   /
#                     |                              [1_1_1] --- [2_2_2] --- [6_6_6]
#                    [15_15_15]                            \
#    ____________                                           \              _______________
#   |            |                 ______                    \            |               |
#  [0_0_0]      [12_12_12]        |      |                     [3_3_3]   [4_4_4]   [23_23_23]
#       |               |         | [9_9_9]                         |_________|
#      [13_13_13]  [7_7_7]        |      |
#              |________|        [18_18_18]
#


class TestCheckOverlap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test class by getting the GFA file to test."""
        try:
            gfa_file = get_gfa_file_from_args("check_overlap")
        except ValueError as e:
            raise unittest.SkipTest(str(e))

        if not should_run_test_for_gfa("check_overlap", gfa_file):
            raise unittest.SkipTest(f"No '# test: check_overlap' comment found in {gfa_file}")

        cls.graph = pygfa.gfa.GFA()
        cls.graph.from_gfa(gfa_file)

    def test_no_external_fasta(self):
        edges_no_consistency = []
        edges_no_calculate = [
            "1_to_2",
            "1_to_3",
            "1_to_5",
            "5_to_8",
            "11_to_14",
            "9_to_18",
            "18_to_9",
            "0_to_12",
            "0_to_13",
            "13_to_7",
        ]
        no_fasta_no_consistency, no_fasta_no_defined = self.graph.overlap_consistency()
        self.assertTrue(no_fasta_no_consistency == edges_no_consistency)
        for edge in edges_no_calculate:
            self.assertTrue(edge in no_fasta_no_defined)

    def test_consistency_true(self):
        edges_no_consistency = []
        edges_no_calculate = []
        correct_no_consistency, correct_no_defined = self.graph.overlap_consistency(
            "data/check_overlap_test_correct.fasta"
        )
        self.assertTrue(correct_no_consistency == edges_no_consistency)
        self.assertTrue(correct_no_defined == edges_no_calculate)

    def test_consistency_false(self):
        edges_no_consistency = ["1_to_2", "1_to_3", "1_to_5", "11_to_14", "0_to_13"]
        edges_no_calculate = ["5_to_8"]
        fail_no_consistency, fail_no_defined = self.graph.overlap_consistency("data/check_overlap_test_fail.fasta")
        for edge in edges_no_consistency:
            self.assertTrue(edge in fail_no_consistency)
        for edge in edges_no_calculate:
            self.assertTrue(edge in fail_no_defined)

    def test_wrong_fasta_file(self):
        file_error = self.graph.overlap_consistency("data/check_overlap_test.fasta")
        self.assertTrue(file_error is None)


if __name__ == "__main__":
    unittest.main()
