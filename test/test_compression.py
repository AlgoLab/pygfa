import sys
import unittest

sys.path.insert(0, "../")

import pygfa
from test_utils import should_run_test_for_gfa, get_gfa_file_from_args

# Before Compression
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

# After Compression
#                                    ______
#                                   |      |                  ___________
#                                   | [9_9_9]                |           |
#                    [14_14_14]     |      |                [5_5_5]     [8_8_8]
#                     |            [18_18_18]               /
# [10'_10'_10'_11_11_11]                                   /
#                     |                              [1_1_1] --- [2_2_2_6_6_6]
#                    [15_15_15]                            \
#    ____________________________________                   \
#   |                                    |                   \
#  [12'_12'_12'_0_0_0_13_13_13]     [7_7_7]                  [3_3_3_4'_4'_4'_23'_23'_23']
#                            |___________|
#


class TestCompression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test class by getting the GFA file to test."""
        try:
            gfa_file = get_gfa_file_from_args("compression")
        except ValueError as e:
            raise unittest.SkipTest(str(e))

        if not should_run_test_for_gfa("compression", gfa_file):
            raise unittest.SkipTest(f"No '# test: compression' comment found in {gfa_file}")

        cls.graph = pygfa.gfa.GFA()
        cls.graph.from_gfa(gfa_file)

    def test_compression(self):
        before_node = [
            "10",
            "11",
            "14",
            "15",
            "9",
            "18",
            "0",
            "12",
            "13",
            "7",
            "1",
            "5",
            "8",
            "2",
            "6",
            "3",
            "4",
            "23",
        ]
        before_edge = [
            ("10", "11"),
            ("11", "14"),
            ("11", "15"),
            ("9", "18"),
            ("18", "9"),
            ("0", "12"),
            ("0", "13"),
            ("13", "7"),
            ("7", "12"),
            ("1", "2"),
            ("1", "3"),
            ("1", "5"),
            ("2", "6"),
            ("3", "4"),
            ("4", "23"),
            ("5", "8"),
        ]
        before_len = [1, 1, 1, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]

        for node in before_node:
            self.assertTrue(node in list(self.graph.nodes()))
        i = 0
        for edge in before_edge:
            self.assertTrue(len(self.graph._search_edge_by_nodes(edge)) == before_len[i])
            i += 1

        self.graph.compression()

        after_node = ["10", "14", "15", "9", "18", "0", "7", "1", "5", "8", "2", "3"]
        removed_node = ["11", "6", "12", "13", "4", "23"]

        after_edge = [
            ("10", "14"),
            ("10", "15"),
            ("9", "18"),
            ("18", "9"),
            ("0", "7"),
            ("7", "0"),
            ("1", "2"),
            ("1", "3"),
            ("1", "5"),
            ("5", "8"),
        ]
        after_len = [1, 1, 2, 2, 2, 2, 1, 1, 1, 1]
        removed_edge = [("10", "11"), ("0", "12"), ("0", "13"), ("2", "6"), ("3", "4"), ("4", "23")]

        for node in after_node:
            self.assertTrue(node in list(self.graph.nodes()))
        for node in removed_node:
            self.assertTrue(node not in list(self.graph.nodes()))
        i = 0
        for edge in after_edge:
            self.assertTrue(len(self.graph._search_edge_by_nodes(edge)) == after_len[i])
            i += 1
        for edge in removed_edge:
            self.assertTrue(self.graph._search_edge_by_nodes(edge) is None)


if __name__ == "__main__":
    unittest.main()
