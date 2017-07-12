import copy
import sys
import logging
sys.path.insert(0, '../')

import networkx as nx
import unittest

from pygfa.graph_element.parser import header, segment, link, path, containment
from pygfa.graph_element.parser import fragment, edge, gap, group
from pygfa.graph_element.parser import line, field_validator as fv
from pygfa.graph_element import node, edge as ge, subgraph as sg
from pygfa import gfa, gfa1_serializer as gs1, gfa2_serializer as gs2

logging.basicConfig(level=logging.DEBUG)

class TestLine (unittest.TestCase):
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
    graph = gfa.GFA()

    def test_serialize_gfa1_node(self):
        self.graph.clear()
        node_ = node.Node.from_line(\
                        segment.SegmentV1.from_string("S\t1\tACGT\tLN:i:42\txx:Z:test"))
        self.graph.add_node(node_)
        self.assertTrue(gs1.serialize_node(node_) == "S\t1\tACGT\tLN:i:42\txx:Z:test")
        self.assertTrue(gs1.serialize_node(self.graph.node("1")) == "S\t1\tACGT\tLN:i:42\txx:Z:test")

        self.graph.clear()
        node_ = node.Node.from_line(\
                        segment.SegmentV1.from_string("S\t1\tACGT"))
        self.graph.add_node(node_)

        self.assertTrue(gs1.serialize_node(node_) == "S\t1\tACGT")
        self.assertTrue(gs1.serialize_node(self.graph.node("1")) == "S\t1\tACGT")

        del (self.graph.node("1")['sequence'])
        self.assertTrue(gs1.serialize_node(self.graph.node("1")) == "")

        invalid_node = copy.deepcopy(node_)
        invalid_node._sequence = None
        self.assertTrue(gs1.serialize_node(invalid_node) == "")

        invalid_node = copy.deepcopy(node_)
        del(invalid_node._sequence)
        self.assertTrue(gs1.serialize_node(invalid_node) == "")
        
        
    def test_serialize_gfa1_edge(self):
        self.graph.clear()
        link_ = ge.Edge.from_line(\
                        link.Link.from_string(\
                                    "L\t1\t+\t3\t+\t12M\tID:Z:1_to_3\txx:Z:test"))

        link_without_id = ge.Edge.from_line(\
                        link.Link.from_string(\
                                    "L\t1\t+\t3\t+\t12M\txx:Z:test"))
            
        containment_ = ge.Edge.from_line(\
                        containment.Containment.from_string(\
                                    "C\t1\t+\t5\t+\t12\t120M\tID:Z:1_to_5\txx:Z:test"))

        containment_with_trace = ge.Edge.from_line(\
                        containment.Containment.from_string(\
                                    "C\t1\t+\t5\t+\t12\t120M\tID:Z:1_to_5\txx:Z:test"))
        containment_with_trace._alignment = "42,42"

        containment_without_id = ge.Edge.from_line(\
                        containment.Containment.from_string(\
                                    "C\t1\t+\t5\t+\t12\t120M\txx:Z:test"))

        fragment_ = ge.Edge.from_line(\
                        fragment.Fragment.from_string(\
                                    "F\t2\tread1+\t0\t42\t12\t55\t*\tid:Z:read1_in_2\txx:Z:test"))
        edge_ = ge.Edge.from_line(\
                        edge.Edge.from_string(\
                                    "E\t2_to_6\t2+\t6+\t0\t122$\t10\t132\t42,42,42\txx:Z:test"))
        gap_ = ge.Edge.from_line(\
                        gap.Gap.from_string(\
                                    "G\t2_to_12\t2-\t12+\t500\t50\txx:Z:test"))

        self.assertTrue(gs1.serialize_edge(link_) == "L\t1\t+\t3\t+\t12M\tID:Z:1_to_3\txx:Z:test")
        self.assertTrue(gs1.serialize_edge(link_without_id) == \
                            "L\t1\t+\t3\t+\t12M\txx:Z:test")
        self.assertTrue(gs1.serialize_edge(containment_) == \
                            "C\t1\t+\t5\t+\t12\t120M\tID:Z:1_to_5\txx:Z:test")

        self.assertTrue(gs1.serialize_edge(containment_with_trace) == \
                            "C\t1\t+\t5\t+\t12\t*\tID:Z:1_to_5\txx:Z:test")

        self.assertTrue(gs1.serialize_edge(containment_without_id) == \
                            "C\t1\t+\t5\t+\t12\t120M\txx:Z:test")
                            
        self.assertTrue(gs1.serialize_edge(fragment_) == "")
        # the edge alignment is a trace, which is not valid in GFA1,
        # so a * is placed.
        self.assertTrue(gs1.serialize_edge(edge_) == "L\t2\t+\t6\t+\t*\tID:Z:2_to_6\txx:Z:test")
        self.assertTrue(gs1.serialize_edge(gap_) == "")

        self.graph.add_edge("L\t1\t+\t3\t+\t12M\tID:Z:1_to_3\txx:Z:test")
        self.graph.add_edge("C\t1\t+\t5\t+\t12\t120M\tID:Z:1_to_5\txx:Z:test")

        # virtual_0 here
        self.graph.add_edge("F\t2\tread1+\t0\t42\t12\t55\t*\tid:Z:read1_in_2\txx:Z:test")
        self.graph.add_edge("E\t2_to_6\t2+\t6+\t0\t122$\t10\t132\t42,42,42\txx:Z:test")
        self.graph.add_edge("G\t2_to_12\t2-\t12+\t500\t50\txx:Z:test")

        # virtual_1 here
        self.graph.add_edge("C\t1\t+\t5\t+\t12\t120M\txx:Z:test")
        # virtual_2 here
        self.graph.add_edge("L\t1\t+\t3\t+\t12M\txx:Z:test")
                                
        self.assertTrue(gs1.serialize_edge(self.graph.edge("1_to_3"), "1_to_3") == \
                            "L\t1\t+\t3\t+\t12M\tID:Z:1_to_3\txx:Z:test")
        self.assertTrue(gs1.serialize_edge(self.graph.edge("1_to_5"), "1_to_5") == \
                            "C\t1\t+\t5\t+\t12\t120M\tID:Z:1_to_5\txx:Z:test")

        self.graph.edge("1_to_5")['alignment'] = "42,42"
        self.assertTrue(gs1.serialize_edge(self.graph.edge("1_to_5"), "1_to_5") == \
                            "C\t1\t+\t5\t+\t12\t*\tID:Z:1_to_5\txx:Z:test")
                            
        self.assertTrue(gs1.serialize_edge(self.graph.edge("virtual_0"), "virtual_0") == "")
        self.assertTrue(gs1.serialize_edge(self.graph.edge("2_to_6"), "2_to_6") == \
                            "L\t2\t+\t6\t+\t*\tID:Z:2_to_6\txx:Z:test")
        self.assertTrue(gs1.serialize_edge(self.graph.edge("2_to_12"), "2_to_12") == "")
        self.assertTrue(gs1.serialize_edge(self.graph.edge("virtual_1"), "virtual_1") == \
                            "C\t1\t+\t5\t+\t12\t120M\txx:Z:test")
        self.assertTrue(gs1.serialize_edge(self.graph.edge("virtual_2"), "virtual_2") == \
                            "L\t1\t+\t3\t+\t12M\txx:Z:test")

                            
    def test_serialize_gfa1_subgraph(self):
        self.graph.clear()
        self.graph.add_node("S\t11\t140\t*\txx:i:11")
        self.graph.add_node("S\t13\t150\t*")
        self.graph.add_edge("E\t11_to_13\t11+\t13+\t20\t140$\t0\t120\t120M")


        path_ = sg.Subgraph.from_line(\
                                path.Path.from_string(\
                                    "P\t15\t11+,13+\t120M"))

        ogroup = sg.Subgraph.from_line(\
                               group.OGroup.from_string(\
                                    "O\t15\t11+ 11_to_13+ 13+\txx:i:-1"))

        ugroup = sg.Subgraph.from_line(\
                               group.UGroup.from_string(\
                                    "U\t16\t11 13 11_to_13 16sub"))

        self.assertTrue(gs1.serialize_subgraph(path_, "path id:15") == \
                            "P\t15\t11+,13+\t120M")
        # overlaps are not defined, so a * is placed instead
        self.assertTrue(gs1.serialize_subgraph(ogroup, "ogroup: 15") == \
                            "P\t15\t11+,11_to_13+,13+\t*\txx:i:-1")
        # elements that don't point to node are removed if a gfa is
        # provided
        self.assertTrue(gs1.serialize_subgraph(ogroup, "ogroup: 15", self.graph) == \
                            "P\t15\t11+,13+\t*\txx:i:-1")

        self.assertTrue(gs1.serialize_subgraph(ugroup, "ugroup: 16", self.graph) == \
                            "")                            

        # test with dictionaries
        self.graph.add_subgraph("P\t15\t11+,13+\t120M")
        self.assertTrue(gs1.serialize_subgraph(self.graph.subgraphs("15").as_dict(), "graph -> path id:15") == \
                            "P\t15\t11+,13+\t120M")
        self.graph.remove_subgraph("15")

        self.graph.add_subgraph("O\t15\t11+ 11_to_13+ 13+\txx:i:-1")
        self.assertTrue(gs1.serialize_subgraph(self.graph.subgraphs("15").as_dict(), "graph -> ogroup id:15") == \
                           "P\t15\t11+,11_to_13+,13+\t*\txx:i:-1")
        self.graph.remove_subgraph("15")

        self.graph.add_subgraph( "O\t15\t11+ 11_to_13+ 13+\txx:i:-1")
        self.assertTrue(gs1.serialize_subgraph(self.graph.subgraphs("15").as_dict(), \
                                                   "graph -> ogroup id:15", \
                                                   self.graph) == "P\t15\t11+,13+\t*\txx:i:-1")
        self.graph.remove_subgraph("15")

        self.graph.add_subgraph( "U\t16\t11 13 11_to_13 16sub")
        self.assertTrue(gs1.serialize_subgraph(self.graph.subgraphs("16").as_dict(), \
                            "graph -> ugroup id:16") == \
                                "")
        self.graph.remove_subgraph("16")


    def test_serialize_gfa1_graph(self):
        self.graph.clear()

        mini_graph = str.join("", ["S\t11\t*\txx:i:11\n", \
                                       "S\t13\t*\n", \
                                       "L\t11\t+\t13\t+\t120M\n", \
                                       "P\t15\t11+,13+\t120M\n"])
        self.graph.from_string(mini_graph)
        same_graph_repr = gs1.serialize_gfa(self.graph)
        same_graph = gfa.GFA()
        same_graph.from_string(same_graph_repr)

        self.assertTrue(self.graph.node() == same_graph.node())
        self.assertTrue(self.graph.edge() == same_graph.edge())
        self.assertTrue(self.graph.subgraphs() == same_graph.subgraphs())
        
################################################################################

    def test_serialize_gfa2_node(self):
        self.graph.clear()
        node_ = node.Node.from_line(\
                        segment.SegmentV1.from_string("S\t1\tACGT\tLN:i:42\txx:Z:test"))
        node_v2 = node.Node.from_line(\
                        segment.SegmentV2.from_string("S\t1\t122\t*\txx:Z:test"))
        self.assertTrue(gs2.serialize_node(node_) == \
                            "S\t1\t42\tACGT\txx:Z:test")
        self.assertTrue(gs2.serialize_node(node_v2) == \
                            "S\t1\t122\t*\txx:Z:test")

        self.graph.add_node(node_)

        self.assertTrue(gs2.serialize_node(\
                            self.graph.node("1"), \
                            "gfa2_node 1 from SegmentV1") == \
                                "S\t1\t42\tACGT\txx:Z:test")
        self.graph.remove_node("1")

        self.graph.add_node(node_v2)
        self.assertTrue(gs2.serialize_node(\
                            self.graph.node("1"), \
                            "gfa2_node 1 from SegmentV2") == \
                            "S\t1\t122\t*\txx:Z:test")
        self.graph.remove_node("1")
        
        self.graph.clear()
        node_ = node.Node.from_line(\
                        segment.SegmentV1.from_string("S\t1\tACGT"))
        self.graph.add_node(node_)

        self.assertTrue(gs2.serialize_node(\
                                node_, \
                                "gfa2 node 1 without length") == \
                            "S\t1\t0\tACGT")
        self.assertTrue(gs2.serialize_node( \
                                self.graph.node("1"), \
                                "gfa2 node 1 without length") == \
                            "S\t1\t0\tACGT")

        del (self.graph.node("1")['sequence'])
        self.assertTrue(gs2.serialize_node(self.graph.node("1")) == "")

        invalid_node = copy.deepcopy(node_)
        invalid_node._sequence = None
        self.assertTrue(gs2.serialize_node(invalid_node) == "")

        invalid_node = copy.deepcopy(node_)
        del(invalid_node._sequence)
        self.assertTrue(gs2.serialize_node(invalid_node) == "")
        
        
    def test_serialize_gfa2_edge(self):
        self.graph.clear()
        link_ = ge.Edge.from_line(\
                        link.Link.from_string(\
                                    "L\t1\t+\t3\t+\t12M\tID:Z:1_to_3\txx:Z:test"))

        link_without_id = ge.Edge.from_line(\
                        link.Link.from_string(\
                                    "L\t1\t+\t3\t+\t12M\txx:Z:test"))
            
        containment_ = ge.Edge.from_line(\
                        containment.Containment.from_string(\
                                    "C\t1\t+\t5\t+\t12\t120M\tID:Z:1_to_5\txx:Z:test"))

        containment_with_trace = ge.Edge.from_line(\
                        containment.Containment.from_string(\
                                    "C\t1\t+\t5\t+\t12\t120M\tID:Z:1_to_5\txx:Z:test"))
        containment_with_trace._alignment = "42,42"

        containment_without_id = ge.Edge.from_line(\
                        containment.Containment.from_string(\
                                    "C\t1\t+\t5\t+\t12\t120M\txx:Z:test"))

        fragment_ = ge.Edge.from_line(\
                        fragment.Fragment.from_string(\
                                    "F\t2\tread1+\t0\t42\t12\t55\t*\tid:Z:read1_in_2"))
        edge_ = ge.Edge.from_line(\
                        edge.Edge.from_string(\
                                    "E\t2_to_6\t2+\t6+\t0\t122$\t10\t132\t42,42,42\txx:Z:test"))
        gap_ = ge.Edge.from_line(\
                        gap.Gap.from_string(\
                                    "G\t2_to_12\t2-\t12+\t500\t50\txx:Z:test"))

        self.assertTrue(gs2.serialize_edge(link_, \
                                               "gfa2 link") == "")
        self.assertTrue(gs2.serialize_edge(link_without_id, \
                                               "gfa2 link2") == "")
        self.assertTrue(gs2.serialize_edge(containment_, \
                                               "gfa2 containment") == "")
        self.assertTrue(gs2.serialize_edge(containment_with_trace, \
                                               "gfa2 containment") == "")
        self.assertTrue(gs2.serialize_edge(containment_without_id, \
                                               "gfa2 containment") == "")
                            
        self.assertTrue(gs2.serialize_edge(\
                        fragment_, \
                        "gfa2 fragment")  == \
                "F\t2\tread1+\t0\t42\t12\t55\t*\tid:Z:read1_in_2")

        # the edge alignment is a trace, which is not valid in GFA1,
        # so a * is placed.
        self.assertTrue(gs2.serialize_edge(\
                        edge_, \
                        "gfa2 edge") == \
                "E\t2_to_6\t2+\t6+\t0\t122$\t10\t132\t42,42,42\txx:Z:test")

        self.assertTrue(gs2.serialize_edge( \
                        gap_, \
                        "gfa2 gap") == \
                "G\t2_to_12\t2-\t12+\t500\t50\txx:Z:test")

        # test dictionaries
        self.graph.add_edge("L\t1\t+\t3\t+\t12M\tID:Z:1_to_3\txx:Z:test")
        self.graph.add_edge("C\t1\t+\t5\t+\t12\t120M\tID:Z:1_to_5\txx:Z:test")
        # virtual_0 here
        self.graph.add_edge("F\t2\tread1+\t0\t42\t12\t55\t*\tid:Z:read1_in_2")
        self.graph.add_edge("E\t2_to_6\t2+\t6+\t0\t122$\t10\t132\t42,42,42\txx:Z:test")
        self.graph.add_edge("G\t2_to_12\t2-\t12+\t500\t50\txx:Z:test")
        # virtual_1 here
        self.graph.add_edge("C\t1\t+\t5\t+\t12\t120M\txx:Z:test")
        # virtual_2 here
        self.graph.add_edge("L\t1\t+\t3\t+\t12M\txx:Z:test")
                                
        self.assertTrue(gs2.serialize_edge(\
                            self.graph.edge("1_to_3"), \
                            "gfa2 link 1_to_3") == "")
        self.assertTrue(gs2.serialize_edge(\
                            self.graph.edge("1_to_5"), \
                            "gfa2 containment 1_to_5") == "")

        self.graph.edge("1_to_5")['alignment'] = "42,42"
        self.assertTrue(gs2.serialize_edge(\
                            self.graph.edge("1_to_5"), \
                            "gfa2 containment: 1_to_5") == "")

        print(gs2.serialize_edge(\
                            self.graph.edge("virtual_0"), \
                            "gfa2 fragment: virtual_0"))
        self.assertTrue(gs2.serialize_edge(\
                            self.graph.edge("virtual_0"), \
                            "gfa2 fragment: virtual_0") == \
                "F\t2\tread1+\t0\t42\t12\t55\t*\tid:Z:read1_in_2")
        self.assertTrue(gs2.serialize_edge(\
                            self.graph.edge("2_to_6"), \
                            "gfa2 edge: 2_to_6") == \
                "E\t2_to_6\t2+\t6+\t0\t122$\t10\t132\t42,42,42\txx:Z:test")
        self.assertTrue(gs2.serialize_edge(\
                            self.graph.edge("2_to_12"), \
                            "gfa2 gap: 2_to_12") == \
                "G\t2_to_12\t2-\t12+\t500\t50\txx:Z:test")
        self.assertTrue(gs2.serialize_edge(\
                            self.graph.edge("virtual_1"), \
                            "gfa2 containment without id: virtual_1") == "")
        self.assertTrue(gs2.serialize_edge(\
                            self.graph.edge("virtual_2"), \
                            "gfa2 link without id: virtual_2") == "")

                            
    def test_serialize_gfa2_subgraph(self):
        self.graph.clear()
        self.graph.add_node("S\t11\t140\t*\txx:i:11")
        self.graph.add_node("S\t13\t150\t*")
        self.graph.add_edge("E\t11_to_13\t11+\t13+\t20\t140$\t0\t120\t120M")


        path_ = sg.Subgraph.from_line(\
                                path.Path.from_string(\
                                    "P\t15\t11+,13+\t120M"))
        ogroup = sg.Subgraph.from_line(\
                               group.OGroup.from_string(\
                                    "O\t15\t11+ 11_to_13+ 13+\txx:i:-1"))
        ugroup = sg.Subgraph.from_line(\
                               group.UGroup.from_string(\
                                    "U\t16\t11 13 11_to_13 16sub"))
        self.assertTrue(gs2.serialize_subgraph(\
                            path_, \
                            "gfa2 path id:15") == \
                        "O\t15\t11+ 13+")
        self.assertTrue(gs2.serialize_subgraph(\
                            ogroup, \
                            "gfa2 ogroup: 15") == \
                        "O\t15\t11+ 11_to_13+ 13+\txx:i:-1")
        self.assertTrue(gs2.serialize_subgraph(\
                            ogroup, \
                            "gfa2 ogroup: 15", \
                            self.graph) == \
                        "O\t15\t11+ 11_to_13+ 13+\txx:i:-1")

        self.assertTrue(gs2.serialize_subgraph(\
                            ugroup, \
                            "ugroup: 16",
                            self.graph) == \
                            "U\t16\t11 13 11_to_13 16sub")

        # test with dictionaries
        self.graph.add_subgraph("P\t15\t11+,13+\t120M")
        self.assertTrue(gs2.serialize_subgraph(\
                            self.graph.subgraphs("15").as_dict(), \
                            "gfa2 graph -> path id:15") == \
                        "O\t15\t11+ 13+")
        self.graph.remove_subgraph("15")

        self.graph.add_subgraph("O\t15\t11+ 11_to_13+ 13+\txx:i:-1")
        self.assertTrue(gs2.serialize_subgraph(\
                            self.graph.subgraphs("15").as_dict(), \
                            "graph -> ogroup id:15") == \
                        "O\t15\t11+ 11_to_13+ 13+\txx:i:-1")
        self.graph.remove_subgraph("15")

        self.graph.add_subgraph("O\t15\t11+ 11_to_13+ 13+\txx:i:-1")
        self.assertTrue(gs2.serialize_subgraph(\
                            self.graph.subgraphs("15").as_dict(), \
                            "graph -> ogroup id:15", \
                            self.graph) == \
                        "O\t15\t11+ 11_to_13+ 13+\txx:i:-1")
        self.graph.remove_subgraph("15")

        self.graph.add_subgraph("U\t16\t11 13 11_to_13 16sub")
        self.assertTrue(gs2.serialize_subgraph(\
                            self.graph.subgraphs("16").as_dict(), \
                            "graph -> ugroup id:16") == \
                        "U\t16\t11 13 11_to_13 16sub")
        self.graph.remove_subgraph("16")


    def test_serialize_gfa2_graph(self):
        self.graph.clear()

        mini_graph = str.join("", ["S\t11\t*\txx:i:11\n", \
                                       "S\t13\t*\n", \
                                       "L\t11\t+\t13\t+\t120M\n", \
                                       "P\t15\t11+,13+\t120M\n"])
        self.graph.from_string(mini_graph)
        same_graph_repr = gs1.serialize_gfa(self.graph)
        same_graph = gfa.GFA()
        same_graph.from_string(same_graph_repr)

        self.assertTrue(self.graph.node() == same_graph.node())
        self.assertTrue(self.graph.edge() == same_graph.edge())
        self.assertTrue(self.graph.subgraphs() == same_graph.subgraphs())

            
if  __name__ == '__main__':
    unittest.main()
