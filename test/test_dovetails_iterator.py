import sys
sys.path.insert(0, '../')

from networkx.exception import NetworkXError
import unittest

import pygfa

gfa_file = str.join("", ["S\ts1\t9\t*\n" \
                        + "S\ts2\t11\t*\n" \
                        + "S\ts3\t23\t*\n" \
                        + "S\ts4\t3\t*\n" \
                        + "S\ts5\t50\t*\n" \
                        + "E\tl12\ts1+\ts2+\t3\t8$\t0\t4\t*\n" \
                        + "E\tl23\ts2-\ts3+\t0\t2\t7\t10$\t*\n" \
                        + "E\tc14\ts1+\ts4+\t5\t7\t0\t2$\t*\n" \
                        + "E\tl15\ts1-\ts5+\t0\t5\t0\t5\t*\n"])

linear_path = str.join("",  ["S\ts1\t9\t*\n" \
                        + "S\ts2\t11\t*\n" \
                        + "S\ts3\t23\t*\n" \
                        + "S\ts4\t3\t*\n" \
                        + "S\ts5\t50\t*\n" \
                        + "S\ts6\t20\t*\n" \
                        + "L\ts1\t+\ts2\t+\t*\n" \
                        + "L\ts2\t+\ts3\t+\t*\n" \
                        + "L\ts3\t+\ts6\t+\t*\n" \
                        + "L\ts6\t+\ts4\t+\t*\n" \
                        + "L\ts1\t+\ts4\t+\t*\n" \
                        + "L\ts4\t+\ts5\t+\t*\n"])

#    s2 --- s3 --- s6
#   /                \
# s1 ---------------- s4 --- s5
#
#
                        

class TestLine (unittest.TestCase):

    graph = pygfa.gfa.GFA()
    graph.from_string(gfa_file)

    def test_is_dovetail(self):
        """Test wheter the edges represent a dovetail overlaps."""
        self.assertTrue(self.graph.edge("l12")['is_dovetail'])
        self.assertTrue(self.graph.edge("l23")['is_dovetail'])
        self.assertTrue(self.graph.edge("l15")['is_dovetail'])
        self.assertTrue(self.graph.edge("c14")['is_dovetail'] == False)

    def test_extreme(self):
        """Test behavior on sequence extremes, right and left iterator,
        degree methods.
        """
        self.assertTrue(self.graph.edge("l12")['from_segment_end'] == "R")
        self.assertTrue(self.graph.edge("l12")['to_segment_end'] == "L")

        self.assertTrue(self.graph.edge("l23")['from_segment_end'] == "L")
        self.assertTrue(self.graph.edge("l23")['to_segment_end'] == "L")

        self.assertTrue(self.graph.edge("l15")['from_segment_end'] == "L")
        self.assertTrue(self.graph.edge("l15")['to_segment_end'] == "L")

        self.assertTrue(set(self.graph.right("s1")) == {"s2"})
        self.assertTrue(set(self.graph.left("s1")) == {"s5"})
        self.assertTrue(self.graph.right_degree("s1") == 1)
        self.assertTrue(self.graph.left_degree("s1") == 1)
        self.assertTrue(set(self.graph.dovetails_neighbors("s1")) == {"s2", "s5"})

        self.assertTrue(set(self.graph.right("s2")) == set())
        self.assertTrue(set(self.graph.left("s2")) == {"s3", "s1"})
        self.assertTrue(self.graph.right_degree("s2") == 0)
        self.assertTrue(self.graph.left_degree("s2") == 2)
        self.assertTrue(set(self.graph.dovetails_neighbors("s2")) == {"s1", "s3"})

        self.assertTrue(set(self.graph.right("s4")) == set())
        self.assertTrue(set(self.graph.left("s4")) == set())
        self.assertTrue(set(self.graph.dovetails_neighbors("s4")) == set())

    def test_dovetails_iter(self):
        data_ = self.graph.edge("l12")
        self.assertTrue(("s1", "s2", "l12") in self.graph.dovetails_iter("s1", keys=True))
        self.assertTrue(("s1", "s2", "l12", data_) in self.graph.dovetails_iter("s1", keys=True, data=True))

        
    def test_dovetails_nbunch_iter(self):
        """Check that this method only returs
        nodes involved into dovetail overlap edges.
        """
        # if nbunch is None return all the consider all the nodes in the graph
        self.assertTrue({"s1", "s2", "s3", "s5"} == set(self.graph.dovetails_nbunch_iter()))
        # s4 correctly missing

        self.assertTrue({"s2", "s5", "s1"} == set(self.graph.dovetails_nbunch_iter(("s1", "s2", "s5"))))

        # s4 is not involved into a dovetail overlap
        self.assertTrue(set() == set(self.graph.dovetails_nbunch_iter("s4")))

        # test single node (just to check the branch in the implementation)
        self.assertTrue({"s2"} == set(self.graph.dovetails_nbunch_iter("s2")))


    def test_dovetails_linear_path_iter(self):
        graph = pygfa.gfa.GFA()
        graph.from_string(linear_path)

        self.assertTrue(set(graph.dovetails_linear_path_traverse_nodes_iter("s3"))
                            == {"s2", "s3", "s6"})

        self.assertTrue(set(graph.dovetails_linear_path_traverse_edges_iter("s2"))
                            == {("s2", "s3"), ("s3", "s6")})

        # from source use BFS
        self.assertTrue(set(graph.dovetails_linear_path_traverse_edges_iter("s3"))
                            == {("s3", "s2"), ("s3", "s6")})

        self.assertTrue(set(graph.dovetails_linear_path_iter("s2"))
                            == {("s2", "s3"), ("s3", "s6")})

        self.assertTrue(set(graph.dovetails_linear_path_iter("s3"))
                            == {("s2", "s3"), ("s3", "s6")}
                        or
                        set(graph.dovetails_linear_path_iter("s3"))
                            == {("s6", "s3"), ("s3", "s2")})

        self.assertTrue(set(graph.dovetails_linear_path_iter("s1")) == set())

        self.assertTrue(set(graph.dovetails_linear_path_iter("42")) == set())

        self.assertTrue(set(graph.dovetails_linear_path_iter("s5")) == set())
        

if  __name__ == '__main__':
    unittest.main()
