import sys
sys.path.insert(0, '../')

from networkx.exception import NetworkXError
import unittest

import pygfa

gfa_file = str.join("", ["S\ts1\t25\t*\n" \
                        + "S\ts2\t21\t*\n" \
                        + "S\ts3\t10\t*\n" \
                        + "S\ts4\t12\t*\n" \
                        + "S\ts5\t21\t*\n" \
                        + "S\ts6\t42\t*\n" \
                        + "S\ts7\t14\t*\n" \
                        + "E\tl12r\ts1+\ts2+\t20\t24$\t0\t4\t*\n" \
                        + "E\tl12l\ts1-\ts2+\t0\t4\t0\t4\t*\n" \
                        + "E\tl23\ts2+\ts3+\t18\t20$\t0\t2\t*\n" \
                        + "E\tl34\ts3-\ts4+\t7\t10$\t0\t3\t*\n" \
                        + "E\tl45\ts4+\ts5+\t9\t11$\t0\t2\t*\n" \
                        + "E\tl35\ts3+\ts5+\t7\t10$\t0\t3\t*\n" \
                        + "E\tgeneric57\ts5+\ts7+\t4\t7\t0\t3\t*\n" \
                        + "E\tl76\ts7+\ts6+\t10\t13$\t0\t4\t*\n"])

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

class TestLine (unittest.TestCase):

    graph = pygfa.gfa.GFA()
    graph.from_string(gfa_file)

    def test_articulation_points(self):
        """Test that the correct articulation points are
        taken into account."""
        self.assertTrue(set(self.graph.neighbors("s7")) == {"s5", "s6"})
        self.assertTrue(set(self.graph.dovetails_neighbors("s7")) == {"s6"})
        self.assertTrue(set(pygfa.dovetails_articulation_points(self.graph)) == {"s2", "s3"})


if  __name__ == '__main__':
    unittest.main()
