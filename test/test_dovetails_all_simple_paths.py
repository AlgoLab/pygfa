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
        if not should_run_test_for_gfa("dovetails_all_simple_paths", GFA_FILE):
            raise unittest.SkipTest(f"No '# test: dovetails_all_simple_paths' comment found in {GFA_FILE}")

        cls.graph = pygfa.gfa.GFA()
        cls.graph.from_gfa(GFA_FILE)

    def test_dovetails_all_simple_paths(self):
        self.assertTrue(
            [("18", "12"), ("12", "9"), ("9", "11"), ("11", "6")]
            in list(pygfa.dovetails_all_simple_paths(self.graph, "18", "6", edges=True))
        )

        self.assertTrue(
            [("18", "23"), ("23", "21"), ("21", "20"), ("20", "16"), ("16", "22"), ("22", "6")]
            in list(pygfa.dovetails_all_simple_paths(self.graph, "18", "6", edges=True))
        )

        self.assertTrue(
            [("18", "19"), ("19", "1"), ("1", "2"), ("2", "8"), ("8", "3"), ("3", "6")]
            in list(pygfa.dovetails_all_simple_paths(self.graph, "18", "6", edges=True))
        )
        self.assertTrue(len(list(pygfa.dovetails_all_simple_paths(self.graph, "18", "6", edges=True))) == 3)
        self.assertTrue(
            ["18", "12", "9", "11", "6"] in list(pygfa.dovetails_all_simple_paths(self.graph, "18", "6", edges=False))
        )

        self.assertTrue(
            ["18", "23", "21", "20", "16", "22", "6"]
            in list(pygfa.dovetails_all_simple_paths(self.graph, "18", "6", edges=False))
        )

        self.assertTrue(
            ["18", "19", "1", "2", "8", "3", "6"]
            in list(pygfa.dovetails_all_simple_paths(self.graph, "18", "6", edges=False))
        )
        self.assertTrue(len(list(pygfa.dovetails_all_simple_paths(self.graph, "18", "6", edges=True))) == 3)


if __name__ == "__main__":
    unittest.main()
