import copy
import os
import sys
import unittest

import networkx as nx

sys.path.insert(0, "../")


from pygfa import gfa
from test_utils import should_run_test_for_gfa
from pygfa.graph_element.parser import segment, link, path, containment
from pygfa.graph_element import node, edge as ge, subgraph as sg

# Load sample GFA files from data directory
_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
GFA_FILE_1 = os.path.join(_DATA_DIR, "example_1.gfa")
with open(GFA_FILE_1, "r") as f:
    sample_gfa1 = f.read()

GFA_FILE_2 = os.path.join(_DATA_DIR, "example_2.gfa")
with open(GFA_FILE_2, "r") as f:
    sample_gfa2 = f.read()


class TestLine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test class by checking if test should run for both GFA files."""
        # Check if test should run for sample_gfa2
        if not should_run_test_for_gfa("gfa_graph", GFA_FILE_2):
            raise unittest.SkipTest(f"No '# test: gfa_graph' comment found in {GFA_FILE_2}")

        # Check if test should run for sample_gfa1
        if not should_run_test_for_gfa("gfa_graph", GFA_FILE_1):
            raise unittest.SkipTest(f"No '# test: gfa_graph' comment found in {GFA_FILE_1}")

    graph = gfa.GFA()

    def test_GFA_graph(self):
        """Test GFA constructor and accessor methods."""
        tmp = gfa.GFA()

        self.assertTrue(tmp._get_virtual_id(increment=False) == 0)
        self.assertTrue(list(tmp.nodes()) == [])
        self.assertTrue(list(tmp.edges()) == [])
        self.assertTrue(tmp.subgraphs() == {})

        tmp_nx = nx.Graph()
        with self.assertRaises(gfa.GFAError):
            gfa.GFA(tmp_nx)

        tmp_nx = nx.DiGraph()
        with self.assertRaises(gfa.GFAError):
            gfa.GFA(tmp_nx)

        tmp_nx = nx.MultiGraph()
        tmp_nx.add_node("2", nid="2", sequence="acgt", slen="4")
        tmp_nx.add_node("4", nid="4", sequence="*", slen="25")
        tmp_nx.add_edge(
            "4",
            "2",
            key="virtual_42",
            eid="*",
            from_node="4",
            to_node="2",
            from_orn="+",
            to_orn="-",
            from_positions=None,
            to_positions=None,
            distance=None,
            variance="*",
        )

        tmp = gfa.GFA(tmp_nx)
        self.assertTrue(len(tmp.nodes()) == 2)
        # return the edges start from each node, there are 2 nodes,
        # so there are 2 entries into the edge dictionary
        self.assertTrue(len(tmp.edges(adj_dict=True)) == 2)
        self.assertTrue(tmp._find_max_virtual_id() == 42)
        self.assertTrue(tmp.nodes(identifier="2")["nid"] == "2")
        self.assertTrue(tmp.nodes(identifier="2")["sequence"] == "acgt")
        self.assertTrue(tmp.nodes(identifier="4")["nid"] == "4")
        self.assertTrue(tmp.nodes(identifier="not_exists") is None)

        # exists an edge between two and 4
        self.assertTrue(len(tmp.edges(identifier=("4", "2"))) == 1)
        self.assertTrue(tmp.edges(identifier=("4", "2", "virtual_42"))["eid"] == "*")
        self.assertTrue(tmp.edges(identifier="None_Key") is None)
        self.assertTrue(tmp.edges(identifier=("4", "None_Node")) is None)

        # with self.assertRaises(gfa.InvalidSearchParameters):
        #     tmp.edge(("4"))
        # this a language issue, this is seen from the interpreter as
        # a string and not a single element tuple.
        with self.assertRaises(gfa.InvalidSearchParameters):
            tmp.edges(identifier=("4",))  # this is a single element tuple

        with self.assertRaises(gfa.InvalidSearchParameters):
            tmp.edges(identifier=())  # this is a single element tuple

        tmp.edges(identifier="virtual_42")["alignment"] = "20M2I4D"
        self.assertTrue(tmp.edges(identifier="virtual_42")["alignment"] == "20M2I4D")

        tmp.nodes(identifier="4")["new_attribute"] = 42
        self.assertTrue(tmp.nodes(identifier="4")["new_attribute"] == 42)

    def test_add_node(self):
        """Test add_node and remove_node methods."""
        self.graph.clear()
        seg = segment.SegmentV1.from_string("S\t3\tTGCAACGTATAGACTTGTCAC\tRC:i:4\tui:Z:test\tab:Z:another_test")
        node_ = node.Node.from_line(seg)
        self.graph.add_node(node_)
        seg.fields["name"]._value = "node4"
        node_ = node.Node.from_line(seg)
        self.graph.add_node(node_)

        self.graph._graph.add_edge("3", "node4")  # create an edge (indirectly)
        self.assertTrue(len(self.graph.edges()) == 1)

        self.assertTrue(len(self.graph.nodes()) == 2)
        self.assertTrue(self.graph.nodes(identifier="3")["sequence"] == "TGCAACGTATAGACTTGTCAC")
        self.assertTrue(self.graph.nodes(identifier="3")["nid"] == "3")
        self.assertTrue(self.graph.nodes(identifier="3")["ui"].value == "test")
        self.assertTrue(self.graph.nodes(identifier="3")["ui"].type == "Z")

        self.graph.remove_node("3")
        self.assertTrue(self.graph.nodes(identifier="3") is None)
        self.assertTrue(len(self.graph.edges()) == 0)
        # the edge between 3 and 4 has been automatically deleted

        self.graph.add_node("S\t3\tTGCAACGTATAGACTTGTCAC\tRC:i:4\tui:Z:test\tab:Z:another_test")
        self.assertTrue(self.graph.nodes(identifier="3")["sequence"] == "TGCAACGTATAGACTTGTCAC")
        self.assertTrue(self.graph.nodes(identifier="3")["nid"] == "3")
        self.assertTrue(self.graph.nodes(identifier="3")["ui"].value == "test")
        self.assertTrue(self.graph.nodes(identifier="3")["ui"].type == "Z")
        self.graph.remove_node("3")

        # test GFA2 segment
        self.graph.add_node("S\t3\t21\tTGCAACGTATAGACTTGTCAC\tRC:i:4\tui:Z:test\tab:Z:another_test")
        self.assertTrue(self.graph.nodes(identifier="3")["sequence"] == "TGCAACGTATAGACTTGTCAC")
        self.assertTrue(self.graph.nodes(identifier="3")["nid"] == "3")
        self.assertTrue(self.graph.nodes(identifier="3")["ui"].value == "test")
        self.assertTrue(self.graph.nodes(identifier="3")["ui"].type == "Z")
        self.assertTrue(self.graph.nodes(identifier="3")["slen"] == 21)

        with self.assertRaises(gfa.GFAError):
            self.graph.add_node("S\t3\t21\tTGCAACGTATAGACTTGTCAC\tRC:i:4\tui:Z:test\tab:Z:another_test", safe=True)

        with self.assertRaises(TypeError):
            self.graph.add_node("21", nid="21", slen="4", sequence="acgt")
        with self.assertRaises(node.InvalidNodeError):
            self.graph.add_node({"nid": "21", "slen": "4", "sequence": "acgt"})

        with self.assertRaises(node.InvalidNodeError):
            self.graph.remove_node("42")

    def test_add_edge(self):
        self.graph.clear()

        self.graph.add_node("S\t3\tTGCAACGTATAGACTTGTCAC\tRC:i:4\tui:Z:test\tab:Z:another_test")
        self.graph.add_node("S\t4\tTGCAACGTATAGACTTGTCAC\tRC:i:4\tui:Z:test\tab:Z:another_test")

        # Add GFA1 link edge
        line = link.Link.from_string("L\t3\t+\t4\t-\t47M\tui:Z:test\tab:Z:another_test")
        edg = ge.Edge.from_line(line)
        self.graph.add_edge(edg)

        # The L line will have virtual id 'virtual_0'
        self.assertTrue(self.graph.edges(identifier=("3", "4"))["virtual_0"]["from_node"] == "3")
        self.assertTrue(self.graph.edges(identifier="virtual_0")["from_node"] == "3")

        self.graph.remove_edge("virtual_0")
        self.assertTrue(self.graph.edges(identifier="virtual_0") is None)

        # nodes will be automatically created
        self.graph.add_edge("L\t3\t+\t65\t-\t47M\tui:Z:test\tab:Z:another_test")
        self.graph.add_edge("C\ta\t+\tb\t-\t10\t*\tui:Z:test\tab:Z:another_test")
        self.assertTrue(len(self.graph.edges()) == 2)

        self.graph.add_edge("L\t3\t+\t65\t-\t47M\tui:Z:test\tID:Z:42")
        with self.assertRaises(gfa.GFAError):
            self.graph.add_edge("L\t3\t+\t65\t-\t47M\tui:Z:test\tID:Z:42", safe=True)
        with self.assertRaises(gfa.GFAError):
            self.graph.add_edge("L\t3\t+\tnon_exists\t-\t47M\tui:Z:test\tID:Z:47", safe=True)

    def test_add_subgraphs(self):
        self.graph.clear()

        line = path.Path.from_string("P\t14\t11+,12+\t122M\tui:Z:test\tab:Z:another_test")
        sb = sg.Subgraph.from_line(line)
        self.graph.add_subgraph(sb)

        with self.assertRaises(gfa.GFAError):
            self.graph.add_subgraph(sb, safe=True)

        self.graph.add_subgraph("O\t15\t11+ 11_to_13+ 13+\txx:i:-1")
        self.graph.add_subgraph("U\t16sub\t2 3\txx:i:-1")
        self.graph.add_subgraph("P\t14_2\t11_2+,12+\t122M\tui:Z:test\tab:Z:another_test")
        self.graph.add_subgraph("O\t*\t11+ 11_to_13+ 13+\txx:i:-1")
        self.assertTrue(len(self.graph.subgraphs()) == 5)

        self.assertTrue(self.graph.subgraphs("virtual_0") is not None)
        self.graph.remove_subgraph("virtual_0")
        self.assertTrue(self.graph.subgraphs("virtual_0") is None)

        with self.assertRaises(sg.InvalidSubgraphError):
            del sb._sub_id
            self.graph.add_subgraph(sb)
        with self.assertRaises(sg.InvalidSubgraphError):
            self.graph.add_subgraph("Z\t14_2\t11_2+,12+\t122M\tui:Z:test\tab:Z:another_test")
        with self.assertRaises(sg.InvalidSubgraphError):
            self.graph.remove_subgraph("42")

    def test_as_graph_element(self):
        self.graph.clear()

        node_ = node.Node.from_line(
            segment.SegmentV1.from_string("S\t3\tTGCAACGTATAGACTTGTCAC\tRC:i:4\tui:Z:test\tab:Z:another_test")
        )
        self.graph.add_node(node_)
        self.assertTrue(self.graph.as_graph_element("3") == node_)

        node_ = node.Node.from_line(
            segment.SegmentV1.from_string("S\t4\tTGCAACGTATAGACTTGTCAC\tRC:i:4\tui:Z:test\tab:Z:another_test")
        )
        self.graph.add_node(node_)
        self.assertTrue(self.graph.as_graph_element("4") == node_)

        node_ = node.Node.from_line(segment.SegmentV2.from_string("S\t2\t120\t*\txx:Z:sometag"))
        self.graph.add_node(node_)
        self.assertTrue(self.graph.as_graph_element("2") == node_)

        # GFA2 features removed - only testing GFA1 features

        edge_ = ge.Edge.from_line(link.Link.from_string("L\t3\t+\t65\t-\t47M\tui:Z:test\tab:Z:another_test"))
        self.graph.add_edge(edge_)
        self.assertTrue(self.graph.as_graph_element("virtual_3") == edge_)

        subgraph_ = sg.Subgraph.from_line(path.Path.from_string("P\t14\t11+,12+\t122M\tui:Z:test\tab:Z:another_test"))
        self.graph.add_subgraph(subgraph_)
        self.assertTrue(self.graph.as_graph_element("14") == subgraph_)

        # GFA2 group features removed - only testing GFA1 features

        with self.assertRaises(gfa.InvalidElementError):
            self.graph.as_graph_element("None_id")

        # force node adding
        self.graph._graph.add_node("id42", some_other_field="42")
        self.assertTrue(self.graph.as_graph_element("id42") is None)

        self.graph._graph.add_node("id42", nid="id42", some_other_field="42")
        self.assertTrue(self.graph.as_graph_element("id42") is None)

    def test_from_string(self):
        self.graph.clear()
        self.graph.from_string(sample_gfa2)
        # 9 effective nodes and 2 node for the external fields in
        # the fragments
        self.assertTrue(len(self.graph.nodes()) == 11)
        self.assertTrue(len(self.graph.edges()) == 10)
        self.assertTrue(len(self.graph.subgraphs()) == 4)

        self.graph.clear()
        self.graph.from_string(sample_gfa1)
        self.assertTrue(len(self.graph.nodes()) == 9)
        self.assertTrue(len(self.graph.edges()) == 6)
        self.assertTrue(len(self.graph.subgraphs()) == 2)

    def test_get_subgraph(self):
        """Get the subgraph labelled 15 from samplefa2."""
        self.graph.clear()
        self.graph.from_string(sample_gfa2)

        subgraph_15 = self.graph.get_subgraph("15")
        self.assertTrue(subgraph_15 is not None)
        self.assertTrue(len(subgraph_15.nodes()) == 2)
        self.assertTrue(len(subgraph_15.edges()) == 1)
        self.assertTrue(subgraph_15.edges(identifier="11_to_13")["alignment"] == "120M")
        self.assertTrue(
            subgraph_15.edges("11_to_13")["alignment"] == self.graph.edges(identifier="11_to_13")["alignment"]
        )

        subgraph_15.edges(identifier="11_to_13")["alignment"] = "42M"
        self.assertTrue(
            subgraph_15.edges(identifier="11_to_13")["alignment"]
            != self.graph.edges(identifier="11_to_13")["alignment"]
        )

        with self.assertRaises(sg.InvalidSubgraphError):
            self.graph.get_subgraph("id42")

    def test_subgraph(self):
        """Test the subgraph interface to networkx method
        `subgraph`."""
        self.graph.clear()
        self.graph.from_string(sample_gfa2)
        subgraph_ = self.graph.subgraph(["1", "3", "11"])
        self.assertTrue(subgraph_ is not None)
        self.assertTrue(isinstance(subgraph_, nx.MultiGraph))
        self.assertTrue(len(subgraph_.nodes()) == 3)
        self.assertTrue(len(subgraph_.edges()) == 2)
        self.assertTrue(subgraph_.get_edge_data("1", "11", "1_to_11") is not None)
        self.assertTrue(subgraph_.get_edge_data("1", "3", "1_to_3") is not None)
        # test copy subgraph
        subgraph_.nodes["3"]["nid"] = 42
        self.assertTrue(subgraph_.nodes["3"] != self.graph.nodes(identifier="3"))

        # create a GFA graph using the subgraph as base graph
        gfa_ = gfa.GFA(subgraph_)
        self.assertTrue(gfa_.edges(identifier="1_to_3") is not None)
        self.assertTrue(subgraph_.get_edge_data("1", "3", "1_to_3") == gfa_.edges(identifier="1_to_3"))

        subgraph_ = self.graph.subgraph(["1", "3", "11"], copy=False)
        subgraph_.nodes["3"]["nid"] = 42
        self.assertTrue(subgraph_.nodes["3"] == self.graph.nodes(identifier="3"))

        # create a GFA graph using the subgraph as base graph
        gfa_ = gfa.GFA(subgraph_)
        self.assertTrue(gfa_.edges(identifier="1_to_3") is not None)
        self.assertTrue(subgraph_.get_edge_data("1", "3", "1_to_3") == gfa_.edges(identifier="1_to_3"))

        subgraph_ = self.graph.subgraph(["1", "3", "11"], copy=False)
        subgraph_.nodes["3"]["nid"] = 42
        self.assertTrue(subgraph_.nodes["3"] == self.graph.nodes(identifier="3"))

    def test_search(self):
        """Perform some query operation on the graph,
        define custom iterator and see the results.

        1. Obtain all edges where `from_node` is 1.
        2. Obtain all the elements that have an xx optfield,
            ignoring its value.
        3. Perform the same operation as point2, but limit the search
            operation on subgraphs.

        4. Obtain all the nodes with 'slen' greater than
            or equal to 140.
        """
        self.graph.clear()
        self.graph.from_string(sample_gfa2)

        result = self.graph.search(lambda element: element["from_node"] == "1", limit_type=gfa.Element.EDGE)
        self.assertTrue("1_to_3" in result)
        self.assertTrue("1_to_11" in result)
        self.assertTrue("1_to_5" in result)
        self.assertTrue("1_to_2" in result)
        self.assertTrue(len(result) == 4)

        result = self.graph.search(lambda element: "xx" in element)
        self.assertTrue("11" in result)
        self.assertTrue("15" in result)
        self.assertTrue("2" in result)
        self.assertTrue(len(result) == 3)
        # A custom line also has xx, but it hasn't been added to the
        # graph.

        result = self.graph.search(lambda element: "xx" in element, limit_type=gfa.Element.SUBGRAPH)
        self.assertTrue("15" in result)
        self.assertTrue(len(result) == 1)

        def greater_than_comparator(element):
            return int(element["slen"]) >= 140

        result = self.graph.search(greater_than_comparator, limit_type=gfa.Element.NODE)
        self.assertTrue("13" in result)
        self.assertTrue("11" in result)
        self.assertTrue("12" in result)
        self.assertTrue("6" in result)
        self.assertTrue(len(result) == 4)

    def test_graph_equality(self):
        self.graph.clear()
        self.graph.from_string(sample_gfa2)
        same_graph = gfa.GFA()
        same_graph.from_string(sample_gfa2)
        self.assertTrue(self.graph == same_graph)
        another_equal_graph = gfa.GFA()
        another_equal_graph.from_string(self.graph.dump(2))
        self.assertTrue(another_equal_graph == self.graph)

        different_node = copy.deepcopy(another_equal_graph)
        different_node.nodes(identifier="3")["sequence"] += "ACGT"
        self.assertFalse(self.graph == different_node)

        # Make end nodes sequence empty and check if
        # virtuals comparison works
        different_edge = copy.deepcopy(another_equal_graph)
        different_edge.nodes(identifier="1")["sequence"] = "*"
        different_edge.nodes(identifier="2")["sequence"] = "*"
        edge_ = different_edge.edges(identifier="1_to_2")
        different_edge.remove_edge("1_to_2")
        different_edge._graph.add_edge("1", "2", key="*", **edge_)
        self.assertFalse(self.graph == different_edge)

        self.graph.clear()
        self.graph.from_string(sample_gfa1)
        same_graph = gfa.GFA()
        same_graph.from_string(sample_gfa1)
        self.assertTrue(self.graph == same_graph)
        another_equal_graph = gfa.GFA()
        another_equal_graph.from_string(self.graph.dump(1))
        self.assertTrue(another_equal_graph == self.graph)

    def test_neighborhood_operation(self):
        self.graph.clear()
        self.graph.from_string(sample_gfa1)

        neighbors_ = self.graph.neighbors("2")
        self.assertTrue("6" in neighbors_)
        self.assertTrue("1" in neighbors_)
        self.assertTrue("5" not in neighbors_)

        with self.assertRaises(gfa.GFAError):
            self.graph.neighbors("42")


if __name__ == "__main__":
    unittest.main()
