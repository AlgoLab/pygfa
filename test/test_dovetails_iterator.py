import os
import sys
import unittest

sys.path.insert(0, "../")

import pygfa
from test_utils import should_run_test_for_gfa

#    s2 --- s3 --- s6
#   /                \
# s1 ---------------- s4 --- s5
#

GFA_FILE = get_test_data_path("test_dovetails_iterator.gfa", "HLA-zoo")


class TestLine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test class by checking if test should run."""
        if not should_run_test_for_gfa("dovetails_iterator", GFA_FILE):
            raise unittest.SkipTest(f"No '# test: dovetails_iterator' comment found in {GFA_FILE}")

        cls.graph = pygfa.gfa.GFA()
        cls.graph.from_gfa(GFA_FILE)

    def test_is_dovetail(self):
        """Test wheter the edges represent a dovetail overlaps."""
        self.assertTrue(self.graph.edges(identifier="l12")["is_dovetail"])
        self.assertTrue(self.graph.edges(identifier="l23")["is_dovetail"])
        self.assertFalse(self.graph.edges(identifier="l15")["is_dovetail"])
        self.assertFalse(self.graph.edges(identifier="c14")["is_dovetail"])

    def test_extreme(self):
        """Test behavior on sequence extremes, right and left iterator,
        degree methods.
        """
        self.assertTrue(self.graph.edges(identifier="l12")["from_segment_end"] == "R")
        self.assertTrue(self.graph.edges(identifier="l12")["to_segment_end"] == "L")

        self.assertTrue(self.graph.edges(identifier="l23")["from_segment_end"] == "R")
        self.assertTrue(self.graph.edges(identifier="l23")["to_segment_end"] == "R")

        self.assertTrue(self.graph.edges(identifier="l15")["from_segment_end"] is None)
        self.assertTrue(self.graph.edges(identifier="l15")["to_segment_end"] is None)

        self.assertTrue(set(self.graph.right("s1")) == {"s2"})
        self.assertTrue(set(self.graph.left("s1")) == set())
        self.assertTrue(self.graph.right_degree("s1") == 1)
        self.assertTrue(self.graph.left_degree("s1") == 0)
        self.assertTrue(set(self.graph.dovetails_neighbors("s1")) == {"s2"})

        self.assertTrue(set(self.graph.right("s2")) == {"s3"})
        self.assertTrue(set(self.graph.left("s2")) == {"s1"})
        self.assertTrue(self.graph.right_degree("s2") == 1)
        self.assertTrue(self.graph.left_degree("s2") == 1)
        self.assertTrue(set(self.graph.dovetails_neighbors("s2")) == {"s1", "s3"})

        self.assertTrue(set(self.graph.right("s4")) == set())
        self.assertTrue(set(self.graph.left("s4")) == set())
        self.assertTrue(set(self.graph.dovetails_neighbors("s4")) == set())

    def test_dovetails_iter(self):
        data_ = self.graph.edges(identifier="l12")
        self.assertTrue(("s1", "s2", "l12") in self.graph.dovetails_iter("s1", keys=True))
        self.assertTrue(("s1", "s2", "l12", data_) in self.graph.dovetails_iter("s1", keys=True, data=True))

    def test_dovetails_nbunch_iter(self):
        """Check that this method only returs
        nodes involved into dovetail overlap edges.
        """
        # if nbunch is None return all the consider all the nodes in the graph
        self.assertTrue({"s1", "s2", "s3"} == set(self.graph.dovetails_nbunch_iter()))
        # s4 correctly missing

        self.assertTrue({"s2", "s1"} == set(self.graph.dovetails_nbunch_iter(("s1", "s2"))))

        # s4 is not involved into a dovetail overlap
        self.assertTrue(set() == set(self.graph.dovetails_nbunch_iter("s4")))

        # test single node (just to check the branch in the implementation)
        self.assertTrue({"s2"} == set(self.graph.dovetails_nbunch_iter("s2")))

    def test_dovetails_linear_path_iter(self):
        graph = pygfa.gfa.GFA()
        linear_path_gfa = os.path.join(os.path.dirname(__file__), "data", "test_linear_path.gfa")

        # Check if this test should run for the linear path GFA
        if not should_run_test_for_gfa("dovetails_iterator", linear_path_gfa):
            self.skipTest(f"No '# test: dovetails_iterator' comment found in {linear_path_gfa}")

        graph.from_gfa(linear_path_gfa)

        self.assertTrue(set(graph.dovetails_linear_path_traverse_nodes_iter("s3")) == {"s2", "s3", "s6"})

        self.assertTrue(set(graph.dovetails_linear_path_traverse_edges_iter("s2")) == {("s2", "s3"), ("s3", "s6")})

        # from source use BFS
        self.assertTrue(set(graph.dovetails_linear_path_traverse_edges_iter("s3")) == {("s3", "s2"), ("s3", "s6")})

        self.assertTrue(set(graph.dovetails_linear_path_iter("s2")) == {("s2", "s3"), ("s3", "s6")})

        self.assertTrue(
            set(graph.dovetails_linear_path_iter("s3")) == {("s2", "s3"), ("s3", "s6")}
            or set(graph.dovetails_linear_path_iter("s3")) == {("s6", "s3"), ("s3", "s2")}
        )

        self.assertTrue(set(graph.dovetails_linear_path_iter("s1")) == set())

        self.assertTrue(set(graph.dovetails_linear_path_iter("42")) == set())

        self.assertTrue(set(graph.dovetails_linear_path_iter("s5")) == set())


if __name__ == "__main__":
    unittest.main()
