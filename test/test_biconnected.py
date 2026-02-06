import os
import sys
from networkx.exception import NetworkXError
import unittest

sys.path.insert(0, "../")

import pygfa

#
# --- = dovetail overlap
# ~~~ = other overlap
#
#     s1
#   s1  \
# s1     [s2_s2_s2_s2] --- [s3_s3_s3] --- [s5_s5_s5] ~~~ [s7_s7_s7_s7] --- [s6_s6_s6]
#   s1  /                 /              /
#    s1                   \             /
#                          [s4_s4_s4]--
#


class TestLine(unittest.TestCase):
    graph = pygfa.gfa.GFA()
    graph.from_gfa(os.path.join(os.path.dirname(__file__), "data", "test_biconnected.gfa"))

    def test_articulation_points(self):
        """Test that the correct articulation points are
        taken into account."""
        self.assertTrue(set(self.graph.neighbors("s7")) == {"s5", "s6"})
        self.assertTrue(set(self.graph.dovetails_neighbors("s7")) == {"s6"})
        self.assertTrue(set(pygfa.dovetails_articulation_points(self.graph)) == {"s2", "s3"})


if __name__ == "__main__":
    unittest.main()
