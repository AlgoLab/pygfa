import sys
import unittest

sys.path.insert(0, "../")

import pygfa
from test_utils import should_run_test_for_gfa, get_test_data_path

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

GFA_FILE = get_test_data_path("test_biconnected.gfa", "HLA-zoo")


class TestLine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test class by checking if test should run."""
        if not should_run_test_for_gfa("biconnected", GFA_FILE):
            raise unittest.SkipTest(f"No '# test: biconnected' comment found in {GFA_FILE}")

        cls.graph = pygfa.gfa.GFA()
        cls.graph.from_gfa(GFA_FILE)

    def test_articulation_points(self):
        """Test that the correct articulation points are
        taken into account."""
        self.assertTrue(set(self.graph.neighbors("s7")) == {"s5", "s6"})


if __name__ == "__main__":
    unittest.main()
