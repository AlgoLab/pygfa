import sys
sys.path.insert(0, '../')

import unittest

import pygfa

gfa_file = str.join("", [\
                    "S\ts1\t25\t*\n", \
                    "S\ts2\t21\t*\n", \
                    "S\ts3\t10\t*\n", \
                    "S\ts4\t12\t*\n", \
                    "S\ts5\t21\t*\n", \
                    "E\tl12\ts1+\ts2+\t20\t24$\t0\t4\t*\n", \
                    "E\tl23\ts2+\ts3+\t18\t20$\t0\t2\t*\n", \
                    "E\tlgeneric34\ts3+\ts4+\t5\t8\t0\t3\t*\n", \
                    "E\tl45\ts4+\ts5+\t9\t11$\t0\t2\t*\n", \
                    "F\tfragment5\ts5+\t10\t14\t100\t104\t*\n", \
                    "S\ts6\t12\t*\n", \
                    "S\ts7\t24\t*\n", \
                    "S\ts8\t9\t*\n", \
                    "E\tl67\ts6+\ts7+\t9\t11$\t0\t2\t*\n"])

#
# --- = dovetail overlap
# ~~~ = other overlap
#
#
# [s1_s1] --- [s2_s2] --- [s3_s3] ~~
#                                  ~~~ [s4_s4] --- [s5_s5]
#
#
# [s6_s6] --- [s7_s7]                [s8_s8_s8]
#

class TestLine (unittest.TestCase):

    graph = pygfa.gfa.GFA()
    graph.from_string(gfa_file)

    def test_nodes_connected_components(self):
        nodes = set(self.graph.nodes())
        self.assertTrue({"s1", "fragment5", "s2", "s3", "s4", "s5"} in \
                            pygfa.nodes_connected_components(self.graph))
        nodes.remove("s1")
        nodes.remove("s2")
        nodes.remove("s3")
        nodes.remove("s4")
        nodes.remove("s5")
        nodes.remove("fragment5")
        self.assertTrue({"s6", "s7"} in \
                            pygfa.nodes_connected_components(self.graph))
        nodes.remove("s6")
        nodes.remove("s7")
        self.assertTrue({"s8"} in \
                            pygfa.nodes_connected_components(self.graph))
        nodes.remove("s8")
        self.assertTrue(nodes == set())


    def test_nodes_connected_component(self):
        self.assertTrue({"s1", "s2", "s3", "s4", "s5", "fragment5"} ==
                            pygfa.nodes_connected_component(self.graph, "s4"))
        with self.assertRaises(pygfa.gfa.GFAError):
            pygfa.nodes_connected_component(self.graph, "42")

if  __name__ == '__main__':
    unittest.main()
