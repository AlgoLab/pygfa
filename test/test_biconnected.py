import sys
import unittest

sys.path.insert(0, "../")

import pygfa
from test_utils import should_run_test_for_gfa, get_gfa_file_from_args

#
# ~~~ = other overlap
#
#     s1
#   s1  \
# s1     [s2_s2_s2_s2] --- [s3_s3_s3] --- [s5_s5_s5] ~~~ [s7_s7_s7_s7] --- [s6_s6_s6]
#   s1  /                 /              /
#    s1                   \             /
#                          [s4_s4_s4]--
#                          [s3_s3_s3]


class TestBiconnected(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test class by getting the GFA file to test."""
        try:
            gfa_file = get_gfa_file_from_args("biconnected")
        except ValueError as e:
            raise unittest.SkipTest(str(e))

        if not should_run_test_for_gfa("biconnected", gfa_file):
            raise unittest.SkipTest(f"No '# test: biconnected' comment found in {gfa_file}")

        cls.graph = pygfa.gfa.GFA.from_gfa(gfa_file)

    def test_articulation_points(self):
        """Test that the correct articulation points are
        taken into account."""
        self.assertTrue(set(self.graph.neighbors("s7")) == {"s5", "s6"})


if __name__ == "__main__":
    unittest.main()
