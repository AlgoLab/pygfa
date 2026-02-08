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


if __name__ == "__main__":
    unittest.main()
