import sys
sys.path.insert(0, '../')

from networkx.exception import NetworkXError
import unittest

import pygfa
from pygfa.dovetail_operations.components.connected import _plain_bfs_dovetails_with_edges

gfa_data_array = [\
                    "S\ts1\t25\t*\n", \
                    "S\ts2\t21\t*\n", \
                    "S\ts3\t10\t*\n", \
                    "S\ts4\t12\t*\n", \
                    "S\ts5\t21\t*\n", \
                    "E\tl12\ts1+\ts2+\t20\t24$\t0\t4\t*\n", \
                    "E\tl23\ts2+\ts3+\t18\t20$\t0\t2\t*\n", \
                    "E\tlgeneric34\ts3+\ts4+\t5\t8\t0\t3\t*\n", \
                    "E\tl45\ts4+\ts5+\t9\t11$\t0\t2\t*\n", \
                    "F\tfragment5\ts5+\t10\t14\t100\t104\t*\n"]

gfa_file = str.join("", gfa_data_array)

gfa_file_sub1 = str.join("", gfa_data_array[0:3] \
                            + gfa_data_array[5:7])

gfa_file_sub2 = str.join("", gfa_data_array[3:5] \
                            + gfa_data_array[8:])

#
# --- = dovetail overlap
# ~~~ = other overlap
#
#
# [s1_s1] --- [s2_s2] --- [s3_s3] ~~
#                                  ~~~ [s4_s4] --- [s5_s5]
#

def graphs_equal(g1, g2):
    """A way to check wheter two graphs
    are equals."""
    if len(g1.nodes()) != len(g2.nodes()) \
      or len(g1.edges()) != len(g2.edges()):
        return False
    try:
        for node_ in g1.nodes_iter():
            if g1.node[node_] != g2.node[node_]:
                return False
        for from_, to_, key in g1.edges_iter(keys=True):
            if g1.edge[from_][to_][key] != g2.edge[from_][to_][key]:
                return False
        return True
    except KeyError:
        return False


class TestLine (unittest.TestCase):

    graph = pygfa.gfa.GFA()
    graph.from_string(gfa_file)

    def test_dovetails_connected_components(self):
        """Test that the correct nodes in the connected components
        taken into account.
        Generate connected components considering dovetail overlap
        edges."""
        self.assertTrue(set(self.graph.neighbors("s4")) == {"s5", "s3"})
        self.assertTrue(set(self.graph.dovetails_neighbors("s4")) == {"s5"})

        # get all the nodes considered in a dovetail overlap
        nodes = set(self.graph.dovetails_nbunch_iter())
        self.assertTrue({"s4", "s5"} in \
                            pygfa.dovetails_nodes_connected_components(self.graph))
        nodes.remove("s4")
        nodes.remove("s5")
        self.assertTrue({"s1", "s2", "s3"} in \
                            pygfa.dovetails_nodes_connected_components(self.graph))
        nodes.remove("s1")
        nodes.remove("s2")
        nodes.remove("s3")
        self.assertTrue(nodes == set())

        # check single component
        self.assertTrue({"s1", "s2", "s3"} == \
                            pygfa.dovetails_nodes_connected_component(self.graph, "s2"))

    def test_dovetails_components_as_subgraphs(self):
        subgraph123 = self.graph.dovetails_subgraph(("s1", "s2", "s3"), copy=True)
        subgraph45 = self.graph.dovetails_subgraph(("s4", "s5"), copy=True)

        self.assertTrue(len(\
                            list(\
                                pygfa.dovetails_connected_components_subgraphs(self.graph))) == 2)
        sub1, sub2 = pygfa.dovetails_connected_components_subgraphs(self.graph)
        if "s1" in sub1:
            self.assertTrue(graphs_equal(sub1, subgraph123))
            self.assertTrue(graphs_equal(sub2, subgraph45))
        else:
            self.assertTrue(graphs_equal(sub2, subgraph123))
            self.assertTrue(graphs_equal(sub1, subgraph45))

    def test_plain_bfs_edges(self):
        self.assertTrue(set([("s2", "s1"), ("s2", "s3")]) == \
                            set(_plain_bfs_dovetails_with_edges(self.graph, "s2")))

if  __name__ == '__main__':
    unittest.main()
