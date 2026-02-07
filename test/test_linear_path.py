import os
import sys
import unittest

sys.path.insert(0, "../")

import pygfa
from test_utils import should_run_test_for_gfa

#
#
#                         [8_8_....     ...        ...          ...           ..8_8]
#            [5         /                                        [13]               \         [10_10]         [24
#    26       5 \      /                                             \               \       /       \        /24
#   /  \      5  [2_2_2]                          [12] --- [9] ------ [11]            [3_3_3]        /       / 24
#  25  27     5 /      \                         /                        \          /       \[4_4_4] --- [7]  24
#   \  /      5]        [1_1_1] --- [19] --- [18]                          [6_6_6_6]                         \ 24
#    28                                          \[23]-[21]-[20]-[16]-[22]/                                   \24]
#
#                 [41_41_41]
#

GFA_FILE = os.path.join(os.path.dirname(__file__), "data", "test_dovetails_all_simple_paths.gfa")


class TestLine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test class by checking if test should run."""
        if not should_run_test_for_gfa("linear_path", GFA_FILE):
            raise unittest.SkipTest(f"No '# test: linear_path' comment found in {GFA_FILE}")

        cls.graph = pygfa.gfa.GFA()
        cls.graph.from_gfa(GFA_FILE)

    def test_dovetails_linear_path(self):
        self.assertTrue(
            [("26", "27"), ("27", "28"), ("28", "25")]
            or [("26", "25"), ("25", "27"), ("27", "28")] == list(pygfa.dovetails_linear_path(self.graph, "26"))
        )
        self.assertTrue([("12", "9")] == list(pygfa.dovetails_linear_path(self.graph, "12")))
        self.assertTrue(
            [("23", "21"), ("21", "20"), ("20", "16"), ("16", "22")]
            == list(pygfa.dovetails_linear_path(self.graph, "21"))
        )
        self.assertTrue([("19", "1")] == list(pygfa.dovetails_linear_path(self.graph, "19")))

    def test_dovetails_linear_paths(self):
        self.assertTrue(len(list(pygfa.dovetails_linear_paths(self.graph))) == 4)


if __name__ == "__main__":
    unittest.main()
