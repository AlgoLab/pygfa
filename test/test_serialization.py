import copy
import logging
import os
import sys
import unittest


sys.path.insert(0, "../")

from pygfa.graph_element.parser import segment, link, path, containment
from pygfa.graph_element import node, edge as ge, subgraph as sg
from pygfa.serializer import gfa1_serializer as gs1
from pygfa import gfa
from test_utils import should_run_test_for_gfa

logging.basicConfig(level=logging.DEBUG)


class TestLine(unittest.TestCase):
    """The main approach is the same, to test the serialization either
    with dictionaries and with objects.

    The dictionaries are taken directly after adding the element to the
    GFA graph, this way it's possible to test the effective goal of the
    serializer.

    For dictionaries, it's tricky to test the opt_field they
    could contain due to the fact that order is not
    guaranteed. So, at least in case of dictionaries, a limit
    of 1 opt_field is taken.

    :Note:
        Especially with the serializer, 100% coverage cannot be expected
        due to the large amount of possible configurations. A general
        coverage either from dictionary and from objects will be the
        main goal.
    """

    @classmethod
    def setUpClass(cls):
        """Set up test class by checking if test should run."""
        # Define the GFA file path used in this test
        _DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
        cls.gfa_file = os.path.join(_DATA_DIR, "test_serialization_mini_graph_gfa1.gfa")

        if not should_run_test_for_gfa("serialization", cls.gfa_file):
            raise unittest.SkipTest(f"No '# test: serialization' comment found in {cls.gfa_file}")

    graph = gfa.GFA()

    def test_serialize_gfa1_node(self):
        self.graph.clear()
        node_ = node.Node.from_line(segment.SegmentV1.from_string("S\t1\tACGT\tLN:i:42\txx:Z:test"))
        self.graph.add_node(node_)
        self.assertTrue(gs1.serialize_node(node_) == "S\t1\tACGT\tLN:i:42\txx:Z:test")
        self.assertTrue(gs1.serialize_node(self.graph.nodes(identifier="1")) == "S\t1\tACGT\tLN:i:42\txx:Z:test")

        self.graph.clear()
        node_ = node.Node.from_line(segment.SegmentV1.from_string("S\t1\tACGT"))
        self.graph.add_node(node_)
        self.assertTrue(gs1.serialize_node(node_) == "S\t1\tACGT")
        self.assertTrue(gs1.serialize_node(self.graph.nodes(identifier="1")) == "S\t1\tACGT")

        self.graph.clear()
        node_ = node.Node.from_line(segment.SegmentV1.from_string("S\t1\t*"))
        self.graph.add_node(node_)
        self.assertTrue(gs1.serialize_node(node_) == "S\t1\t*")
        self.assertTrue(gs1.serialize_node(self.graph.nodes(identifier="1")) == "S\t1\t*")

    def test_serialize_gfa1_edge(self):
        # Test Link
        link_ = ge.Edge.from_line(link.Link.from_string("L\t1\t+\t2\t-\t12M\txx:Z:test"))
        self.assertTrue(gs1.serialize_edge(link_) == "L\t1\t+\t2\t-\t12M\txx:Z:test")

        # Test Containment
        containment_ = ge.Edge.from_line(containment.Containment.from_string("C\t1\t+\t2\t-\t12\t12M\txx:Z:test"))
        self.assertTrue(gs1.serialize_edge(containment_) == "C\t1\t+\t2\t-\t12\t12M\txx:Z:test")

        # Test Containment with trace (Not part of GFA1, but we handle it)
        containment_with_trace = ge.Edge.from_line(
            containment.Containment.from_string("C\t1\t+\t2\t-\t12\t42,42,42\txx:Z:test")
        )
        self.assertTrue(gs1.serialize_edge(containment_with_trace) == "C\t1\t+\t2\t-\t12\t42,42,42\txx:Z:test")

        # Test Link without id (virtual edge)
        link_without_id = ge.Edge.from_line(link.Link.from_string("L\t1\t+\t2\t-\t12M"))
        self.assertTrue(gs1.serialize_edge(link_without_id) == "L\t1\t+\t2\t-\t12M")

        # Test Containment without id (virtual edge)
        containment_without_id = ge.Edge.from_line(containment.Containment.from_string("C\t1\t+\t2\t-\t12"))
        self.assertTrue(gs1.serialize_edge(containment_without_id) == "C\t1\t+\t2\t-\t12")

        # Test from graph
        self.graph.clear()
        link_ = ge.Edge.from_line(link.Link.from_string("L\t1\t+\t2\t-\t12M\txx:Z:test"))
        self.graph.add_edge(link_)
        self.assertTrue(gs1.serialize_edge(self.graph.edges(identifier="virtual_0")) == "L\t1\t+\t2\t-\t12M\txx:Z:test")

        self.graph.clear()
        containment_ = ge.Edge.from_line(containment.Containment.from_string("C\t1\t+\t2\t-\t12"))
        self.graph.add_edge(containment_)
        self.assertTrue(gs1.serialize_edge(self.graph.edges(identifier="virtual_0")) == "C\t1\t+\t2\t-\t12")

        # Test Link with optional fields
        self.graph.clear()
        link_ = ge.Edge.from_line(link.Link.from_string("L\t1\t+\t2\t-\t*\txx:Z:test\tyy:i:42"))
        self.graph.add_edge(link_)
        serialized = gs1.serialize_edge(self.graph.edges(identifier="virtual_0"))
        # Order of optional fields is not guaranteed, so check both possibilities
        self.assertTrue(
            serialized == "L\t1\t+\t2\t-\t*\txx:Z:test\tyy:i:42" or serialized == "L\t1\t+\t2\t-\t*\tyy:i:42\txx:Z:test"
        )

    def test_serialize_gfa1_subgraph(self):
        # Test Path
        path_ = sg.Subgraph.from_line(path.Path.from_string("P\t15\t11+,13+\txx:i:-1"))
        self.assertTrue(gs1.serialize_subgraph(path_) == "P\t15\t11+,13+\txx:i:-1")

        # Test from graph
        self.graph.clear()
        path_ = sg.Subgraph.from_line(path.Path.from_string("P\t15\t11+,13+\txx:i:-1"))
        self.graph.add_subgraph(path_)
        self.assertTrue(gs1.serialize_subgraph(self.graph.subgraphs("15").as_dict()) == "P\t15\t11+,13+\txx:i:-1")

    def test_serialize_gfa1_graph(self):
        _DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
        with open(os.path.join(_DATA_DIR, "test_serialization_mini_graph_gfa1.gfa"), "r") as f:
            gfa1_str = f.read()
        self.graph.clear()
        self.graph.from_string(gfa1_str)
        serialized = gs1.serialize_graph(self.graph)
        # Compare ignoring whitespace differences
        self.assertEqual(
            [line.strip() for line in serialized.split("\n") if line.strip()],
            [line.strip() for line in gfa1_str.split("\n") if line.strip()],
        )


if __name__ == "__main__":
    unittest.main()
