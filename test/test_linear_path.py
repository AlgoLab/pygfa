import sys
import unittest

sys.path.insert(0, "../")

import pygfa
from test_utils import should_run_test_for_gfa, get_gfa_file_from_args

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


class TestLinearPath(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test class by getting the GFA file to test."""
        try:
            gfa_file = get_gfa_file_from_args("linear_path")
        except ValueError as e:
            raise unittest.SkipTest(str(e))

        if not should_run_test_for_gfa("linear_path", gfa_file):
            raise unittest.SkipTest(f"No '# test: linear_path' comment found in {gfa_file}")

        cls.graph = pygfa.gfa.GFA()
        cls.graph.from_gfa(gfa_file)


if __name__ == "__main__":
    unittest.main()
