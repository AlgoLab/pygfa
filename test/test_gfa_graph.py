import copy
import sys
sys.path.insert(0, '../')

import networkx as nx
import unittest

import pygfa

from pygfa import gfa
from pygfa.graph_element.parser import header, segment, link, path, containment
from pygfa.graph_element.parser import fragment, edge, gap, group
from pygfa.graph_element.parser import line, field_validator as fv
from pygfa.graph_element import node, edge as ge, subgraph as sg

sample_gfa2 = str.join("", ['# File used for the collections test\n#', \
                ' similar but NOT equivalent to the gfa1 file!\n' \
                'S\t1\t122\t*\n', \
                'S\t3\t29\tTGCTAGCTGACTGTCGATGCTGTGTG\n', \
                'E\t1_to_2\t1+\t2+\t110\t122$\t0\t12\t12M\n', \
                'S\t5\t130\t*\n', \
                'S\t13\t150\t*\n', \
                'E\t2_to_6\t2+\t6+\t0\t122$\t10\t132\t122M\n', \
                'O\t14\t11+ 12+\n', \
                'S\t11\t140\t*\txx:i:11\n', \
                'F\t2\tread1+\t0\t42\t12\t55\t*\tid:Z:read1_in_2\n', \
                'F\t2\tread2+\t45\t62\t0\t18\t*\tid:Z:read2_in_2\n', \
                'U\t16\t1 3 15 2_to_6 16sub\n', \
                'H\tac:Z:test2\n', \
                '# another comment\n', \
                'S\t12\t150\t*\n', \
                'S\t4\t120\t*\n', \
                'H\tVN:Z:2.0\n', \
                'E\t1_to_3\t1+\t3+\t112\t122$\t0\t12\t10M\n', \
                'G\t1_to_11\t1+\t11-\t120\t*\n', \
                'E\t11_to_12\t11+\t12+\t18\t140$\t0\t122\t122M\n', \
                'S\t6\t150\t*\n', \
                'X\tcustom_record\txx:Z:testtag\n', \
                'X\tcustom_record\tX2\n', \
                'E\t11_to_13\t11+\t13+\t20\t140$\t0\t120\t120M\n', \
                'G\t2_to_12\t2-\t12+\t500\t50\n', \
                'O\t15\t11+ 11_to_13+ 13+\txx:i:-1\n', \
                'Y\tanother_custom_record\n', \
                'U\t16sub\t2 3\n', \
                'S\t2\t120\t*\txx:Z:sometag\n', \
                'H\taa:i:12\tab:Z:test1\n', \
                'H\taa:i:15\n', \
                'E\t1_to_5\t1+\t5+\t0\t122$\t2\t124\t*\tzz:Z:tag\n'])

                
sample_gfa1 = str.join("", ['S\t1\t*\n', \
                'S\t3\tCGATGCTAGCTGACTGTCGATGCTGTGTG\n', \
                'L\t1\t+\t2\t+\t12M\tID:Z:1_to_2\n', \
                'S\t5\t*\n', \
                'S\t13\t*\n', \
                'C\t2\t+\t6\t+\t10\t122M\tID:Z:2_to_6\n', \
                'P\t14\t11+,12+\t122M\n', \
                'S\t11\t*\n', \
                'H\tac:Z:test2\n', \
                'S\t12\t*\n', \
                'S\t4\t*\n', \
                'H\tVN:Z:1.0\n', \
                'L\t1\t+\t3\t+\t12M\tID:Z:1_to_3\n', \
                'L\t11\t+\t12\t+\t122M\tID:Z:11_to_12\n', \
                'S\t6\t*\n', \
                'L\t11\t+\t13\t+\t120M\tID:Z:11_to_13\n', \
                'P\t15\t11+,13+\t120M\n', \
                'S\t2\t*\txx:Z:sometag\n', \
                'H\taa:i:12\tab:Z:test1\n', \
                'H\taa:i:15\n', \
                'C\t1\t+\t5\t+\t12\t120M\tID:Z:1_to_5\n'])


class TestLine (unittest.TestCase):

    graph = gfa.GFA ()


    def test_GFA_graph(self):
        """Test GFA constructor and accessor methods.
        """
        tmp = gfa.GFA()

        self.assertTrue(tmp._get_virtual_id(increment=False) == 0)
        self.assertTrue(tmp.nodes() == [])
        self.assertTrue(tmp.edges() == [])
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
        tmp_nx.add_edge("4", "2", key= "virtual_42", eid="*", \
                        from_node="4", to_node="2", \
                        from_orn="+", to_orn="-", \
                        from_positions=None, to_positions=None, \
                        distance=None, variance="*")

        tmp = gfa.GFA(tmp_nx)
        self.assertTrue(len(tmp.node()) == 2)
        # return the edges start from each node, there are 2 nodes,
        # so there are 2 entries into the edge dictionary
        self.assertTrue(len(tmp.edge()) == 2)
        self.assertTrue(tmp._find_max_virtual_id() == 42)
        self.assertTrue(tmp.node("2")["nid"] == "2")
        self.assertTrue(tmp.node("2")["sequence"] == "acgt")
        self.assertTrue(tmp.node("4")["nid"] == "4")
        self.assertTrue(tmp.node("not_exists") == None)
                            
        # exists an edge between two and 4
        self.assertTrue(len(tmp.edge(("4", "2"))) == 1) 
        self.assertTrue(tmp.edge(("4", "2", "virtual_42"))["eid"] == "*")
        self.assertTrue(tmp.edge("None_Key") == None)
        self.assertTrue(tmp.edge(("4", "None_Node")) == None)

        # with self.assertRaises(gfa.InvalidSearchParameters):
        #     tmp.edge(("4"))
        # this a language issue, this is seen from the interpreter as
        # a string and not a single element tuple.
        with self.assertRaises(gfa.InvalidSearchParameters):
             tmp.edge(("4", )) # this is a single element tuple

        with self.assertRaises(gfa.InvalidSearchParameters):
            tmp.edge(()) # this is a single element tuple


        tmp.edge("virtual_42")['alignment'] = "20M2I4D"
        self.assertTrue(tmp.edge("virtual_42")['alignment'] == "20M2I4D")

        tmp.node("4")["new_attribute"] = 42
        self.assertTrue(tmp.node("4")["new_attribute"] == 42)
        
        
    
    def test_add_node (self):
        """Test add_node and remove_node methods."""
        self.graph.clear ()
        seg = segment.SegmentV1.from_string ("S\t3\tTGCAACGTATAGACTTGTCAC\tRC:i:4\tui:Z:test\tab:Z:another_test")
        node_ = node.Node.from_line (seg)
        self.graph.add_node (node_)
        seg.fields['name']._value = "node4"
        node_ = node.Node.from_line(seg)
        self.graph.add_node (node_)
        
        self.graph._graph.add_edge("3", "node4") # create an edge (indirectly)
        self.assertTrue(len(self.graph.edges()) == 1)

        self.assertTrue (len (self.graph.nodes ()) == 2)
        self.assertTrue (self.graph.node('3')['sequence'] == "TGCAACGTATAGACTTGTCAC")
        self.assertTrue (self.graph.node('3')['nid'] == "3")
        self.assertTrue (self.graph.node('3')['ui'].value == "test")
        self.assertTrue (self.graph.node('3')['ui'].type == "Z")

        self.graph.remove_node("3")
        self.assertTrue(self.graph.node("3") == None)
        self.assertTrue(len(self.graph.edges()) == 0)
        # the edge between 3 and 4 has been automatically deleted

        self.graph.add_node("S\t3\tTGCAACGTATAGACTTGTCAC\tRC:i:4\tui:Z:test\tab:Z:another_test")
        self.assertTrue (self.graph.node('3')['sequence'] == "TGCAACGTATAGACTTGTCAC")
        self.assertTrue (self.graph.node('3')['nid'] == "3")
        self.assertTrue (self.graph.node('3')['ui'].value == "test")
        self.assertTrue (self.graph.node('3')['ui'].type == "Z")
        self.graph.remove_node("3")

        # test GFA2 segment
        self.graph.add_node("S\t3\t21\tTGCAACGTATAGACTTGTCAC\tRC:i:4\tui:Z:test\tab:Z:another_test")
        self.assertTrue (self.graph.node('3')['sequence'] == "TGCAACGTATAGACTTGTCAC")
        self.assertTrue (self.graph.node('3')['nid'] == "3")
        self.assertTrue (self.graph.node('3')['ui'].value == "test")
        self.assertTrue (self.graph.node('3')['ui'].type == "Z")
        self.assertTrue (self.graph.node('3')['slen'] == 21)

        with self.assertRaises(gfa.GFAError):
            self.graph.add_node(\
                "S\t3\t21\tTGCAACGTATAGACTTGTCAC\tRC:i:4\tui:Z:test\tab:Z:another_test",
                safe=True)
        
        with self.assertRaises(TypeError):
            self.graph.add_node("21", nid="21", slen="4", sequence="acgt")
        with self.assertRaises(node.InvalidNodeError):
            self.graph.add_node({'nid':"21", 'slen':"4", 'sequence':"acgt"})

        with self.assertRaises(node.InvalidNodeError):
            self.graph.remove_node("42")


    def test_add_edge (self):
        self.graph.clear ()

        self.graph.add_node("S\t3\tTGCAACGTATAGACTTGTCAC\tRC:i:4\tui:Z:test\tab:Z:another_test")
        self.graph.add_node("S\t4\tTGCAACGTATAGACTTGTCAC\tRC:i:4\tui:Z:test\tab:Z:another_test")

        line = fragment.Fragment.from_string ("F\t3\t4-\t0\t140$\t0\t140\t11M")
        edg = ge.Edge.from_line (line)
        self.graph.add_edge (edg)

        line = link.Link.from_string ("L\t3\t+\t4\t-\t47M\tui:Z:test\tab:Z:another_test")
        edg = ge.Edge.from_line (line)
        self.graph.add_edge (edg)

        # The F line is added first so it will have id 'virtual_0'
        # This first test get all the edges between node 3 and 4 and
        # the get the edge labelled 'virtual_0'
        self.assertTrue (self.graph.edge(('3','4'))['virtual_0']['from_node'] == "3")
        # This test instead get instantly the edge labelled 'virtual_0', that is unique
        # in the graph
        self.assertTrue (self.graph.edge('virtual_0')['from_node'] == "3")
        self.assertTrue (len (self.graph.edge(('3', '4'))) == 2)

        self.graph.remove_edge("virtual_0")
        self.assertTrue (self.graph.edge('virtual_0') == None)
        with self.assertRaises(ge.InvalidEdgeError):
            self.graph.remove_edge("virtual_0")

        # remember the virtual id keeps incrementing
        self.graph.add_edge("F\t3\t4-\t0\t140$\t0\t140\t11M")
        self.assertTrue (self.graph.edge(('3','4'))['virtual_1']['from_node'] == "3")
        self.graph.remove_edge(('3', '4')) # remove all the edges between 3 and 4
        print(len(self.graph.edges()))
        self.assertTrue(len(self.graph.edges()) == 0)

        # nodes will be automatically created
        self.graph.add_edge("L\t3\t+\t65\t-\t47M\tui:Z:test\tab:Z:another_test")
        self.graph.add_edge("C\ta\t+\tb\t-\t10\t*\tui:Z:test\tab:Z:another_test")
        self.graph.add_edge("E\t*\t23-\t16+\t0\t11\t0\t11\t11M\tui:Z:test\tab:Z:another_test")
        self.graph.add_edge("G\tg\tA+\tB-\t1000\t*\tui:Z:test\tab:Z:another_test")
        self.assertTrue(len(self.graph.edges()) == 4)

        self.graph.remove_edge(("A", "B", "g")) # remove the gap
        self.assertTrue(len(self.graph.edges()) == 3)

        self.graph.add_edge("L\t3\t+\t65\t-\t47M\tui:Z:test\tID:Z:42")
        with self.assertRaises(gfa.GFAError):
            self.graph.add_edge(\
                "L\t3\t+\t65\t-\t47M\tui:Z:test\tID:Z:42", \
                safe=True)
        with self.assertRaises(gfa.GFAError):
            self.graph.add_edge(\
                "L\t3\t+\tnon_exists\t-\t47M\tui:Z:test\tID:Z:47", \
                safe=True)

        line = fragment.Fragment.from_string ("F\t3\t4-\t0\t140$\t0\t140\t11M")
        edg = ge.Edge.from_line (line)
        del(edg._eid)
        with self.assertRaises(ge.InvalidEdgeError):
            self.graph.add_edge (edg)
        with self.assertRaises(ge.InvalidEdgeError):
            self.graph.add_edge ("Z\t3\t4-\t0\t140$\t0\t140\t11M") # invalid line


    def test_add_subgraphs (self):
        self.graph.clear ()
        
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

        self.assertTrue(self.graph.subgraphs('virtual_0') is not None)
        self.graph.remove_subgraph("virtual_0")
        self.assertTrue(self.graph.subgraphs('virtual_0') is None)

        with self.assertRaises(sg.InvalidSubgraphError):
            del(sb._sub_id)
            self.graph.add_subgraph(sb)
        with self.assertRaises(sg.InvalidSubgraphError):
            self.graph.add_subgraph("Z\t14_2\t11_2+,12+\t122M\tui:Z:test\tab:Z:another_test")
        with self.assertRaises(sg.InvalidSubgraphError):
            self.graph.remove_subgraph("42")
        

    def test_as_graph_element (self):
        self.graph.clear ()

        node_ = node.Node.from_line(\
                        segment.SegmentV1.from_string(\
                                "S\t3\tTGCAACGTATAGACTTGTCAC\tRC:i:4\tui:Z:test\tab:Z:another_test"))
        self.graph.add_node(node_)
        self.assertTrue (self.graph.as_graph_element('3') == node_)

        node_ = node.Node.from_line(\
                        segment.SegmentV1.from_string(\
                                "S\t4\tTGCAACGTATAGACTTGTCAC\tRC:i:4\tui:Z:test\tab:Z:another_test"))
        self.graph.add_node(node_)
        self.assertTrue (self.graph.as_graph_element('4') == node_)

        node_ = node.Node.from_line(\
                        segment.SegmentV2.from_string(\
                                "S\t2\t120\t*\txx:Z:sometag"))
        self.graph.add_node(node_)
        self.assertTrue (self.graph.as_graph_element('2') == node_)

        edge_ = ge.Edge.from_line(\
                        fragment.Fragment.from_string(\
                                "F\t3\t4-\t0\t140$\t0\t140\t11M"))
        self.graph.add_edge(edge_)
        self.assertTrue (self.graph.as_graph_element ('virtual_0') == edge_)

        edge_ = ge.Edge.from_line(\
                        gap.Gap.from_string(\
                                "G\tg\t3+\t4-\t1000\t*\tui:Z:test\tab:Z:another_test"))
        self.graph.add_edge(edge_)
        self.assertTrue (self.graph.as_graph_element ('g') == edge_)

        edge_ = ge.Edge.from_line(\
                        edge.Edge.from_string(\
                                "E\t*\t23-\t16+\t0\t11\t0\t11\t11M\tui:Z:test\tab:Z:another_test"))
        self.graph.add_edge(edge_)
        self.assertTrue (self.graph.as_graph_element ('virtual_1') == edge_)

        edge_ = ge.Edge.from_line(\
                       containment.Containment.from_string (\
                                "C\ta\t+\tb\t-\t10\t*\tui:Z:test\tab:Z:another_test"))
        self.graph.add_edge(edge_)
        self.assertTrue (self.graph.as_graph_element ('virtual_2') == edge_)

        edge_ = ge.Edge.from_line(\
                       link.Link.from_string(\
                                "L\t3\t+\t65\t-\t47M\tui:Z:test\tab:Z:another_test"))
        self.graph.add_edge(edge_)
        self.assertTrue (self.graph.as_graph_element ('virtual_3') == edge_)

        subgraph_ = sg.Subgraph.from_line(\
                       path.Path.from_string(\
                                "P\t14\t11+,12+\t122M\tui:Z:test\tab:Z:another_test"))
        self.graph.add_subgraph(subgraph_)
        self.assertTrue (self.graph.as_graph_element ('14') == subgraph_)

        subgraph_ = sg.Subgraph.from_line(\
                       group.OGroup.from_string(\
                                "O\t15\t11+ 11_to_13+ 13+\txx:i:-1"))
        self.graph.add_subgraph(subgraph_)
        self.assertTrue (self.graph.as_graph_element ('15') == subgraph_)

        subgraph_ = sg.Subgraph.from_line(\
                      group.UGroup.from_string(\
                                "U\t16sub\t2 3\txx:i:-1"))
        self.graph.add_subgraph(subgraph_)
        self.assertTrue (self.graph.as_graph_element ('16sub') == subgraph_)

        with self.assertRaises(gfa.InvalidElementError):
            self.graph.as_graph_element('None_id')

        # force node adding
        self.graph._graph.add_node("id42", some_other_field="42")
        self.assertTrue(self.graph.as_graph_element("id42") is None)

        self.graph._graph.add_node("id42", nid="id42", some_other_field="42")
        self.assertTrue(self.graph.as_graph_element("id42") is None)



    def test_from_string (self):
        self.graph.clear()
        self.graph.from_string(sample_gfa2)
        # 9 effective nodes and 2 node for the external fields in
        # the fragments
        self.assertTrue(len(self.graph.nodes()) ==  11)
        self.assertTrue(len(self.graph.edges()) ==  10)
        self.assertTrue(len(self.graph.subgraphs()) ==  4)

        self.graph.clear()
        self.graph.from_string(sample_gfa1)
        self.assertTrue(len(self.graph.nodes()) ==  9)
        self.assertTrue(len(self.graph.edges()) ==  6)
        self.assertTrue(len(self.graph.subgraphs()) ==  2)


    def test_get_subgraph(self):
        """Get the subgraph labelled 15 from samplefa2."""
        self.graph.clear()
        self.graph.from_string(sample_gfa2)

        subgraph_15 = self.graph.get_subgraph("15")
        self.assertTrue(subgraph_15 is not None)
        self.assertTrue(len(subgraph_15.nodes()) == 2)
        self.assertTrue(len(subgraph_15.edges()) == 1)
        self.assertTrue(subgraph_15.edge("11_to_13")['alignment'] == "120M")
        self.assertTrue(subgraph_15.edge("11_to_13")['alignment'] == \
                            self.graph.edge("11_to_13")['alignment'])

        subgraph_15.edge("11_to_13")['alignment'] = "42M"
        self.assertTrue(subgraph_15.edge("11_to_13")['alignment'] != \
                            self.graph.edge("11_to_13")['alignment'])

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
        self.assertTrue(subgraph_.edge["1"]["11"]["1_to_11"] is not None)
        self.assertTrue(subgraph_.edge["1"]["3"]["1_to_3"] is not None)
        # test copy subgraph
        subgraph_.node["3"]["nid"] = 42
        self.assertTrue(subgraph_.node["3"] != self.graph.node("3"))

        # create a GFA graph using the subgraph as base graph
        gfa_ = gfa.GFA(subgraph_)
        self.assertTrue(gfa_.edge("1_to_3") is not None)
        self.assertTrue(subgraph_.edge["1"]["3"]["1_to_3"] == \
                             gfa_.edge("1_to_3"))

        subgraph_ = self.graph.subgraph(["1", "3", "11"], copy=False)
        subgraph_.node["3"]["nid"] = 42
        self.assertTrue(subgraph_.node["3"] == self.graph.node("3"))

    def test_dovetails_subgraph(self):
        """Use the dovetails_subgraph method on
        a GFA1 file, and test wheter the subgraphs
        contains edges that are not dovetails overlap
        edges.
        """
        self.graph.clear()
        self.graph.from_string(sample_gfa1)
        subgraph_ = self.graph.dovetails_subgraph()
        self.assertTrue(subgraph_ is not None)
        self.assertTrue(isinstance(subgraph_, nx.MultiGraph))
        self.assertTrue(len(subgraph_.nodes()) == 9)
        self.assertTrue(len(subgraph_.edges()) == 4)
        self.assertTrue(subgraph_.edge["1"]["2"]["1_to_2"] is not None)
        self.assertTrue(subgraph_.edge["1"]["3"]["1_to_3"] is not None)
        self.assertTrue(subgraph_.edge["11"]["13"]["11_to_13"] is not None)
        self.assertTrue(subgraph_.edge["11"]["12"]["11_to_12"] is not None)

        with self.assertRaises(KeyError):
            self.assertTrue(subgraph_.edge["2"]["6"]["2_to_6"] is None)
        with self.assertRaises(KeyError):
            self.assertTrue(subgraph_.edge["1"]["5"]["1_to_5"] is None)
        
        # test copy subgraph
        subgraph_.node["1"]["nid"] = 42
        self.assertTrue(subgraph_.node["1"] != self.graph.node("1"))

        # create a GFA graph using the subgraph as base graph
        gfa_ = gfa.GFA(subgraph_)
        self.assertTrue(gfa_.edge("1_to_3") is not None)
        self.assertTrue(subgraph_.edge["1"]["3"]["1_to_3"] == \
                             gfa_.edge("1_to_3"))

        subgraph_ = self.graph.subgraph(["1", "3", "11"], copy=False)
        subgraph_.node["3"]["nid"] = 42
        self.assertTrue(subgraph_.node["3"] == self.graph.node("3"))


    # :TODO: move test method
    def test_node_connected_component(self):
        """Test of `node_connected_component`.
        Consider the sample_gfa1 graph.       
        """
        self.graph.clear()
        self.graph.from_string(sample_gfa1)

        sub_1 = gfa.GFA(self.graph.subgraph(pygfa.node_connected_component(self.graph, "1")))
        self.assertTrue(sub_1.node("1") is not None)
        self.assertTrue(sub_1.node("5") is not None)
        self.assertTrue(sub_1.node("2") is not None)
        self.assertTrue(sub_1.node("6") is not None)
        self.assertTrue(sub_1.node("3") is not None)

        with self.assertRaises(gfa.GFAError):
            pygfa.node_connected_component(self.graph, 42)

    # :TODO: move test method
    def test_connected_components(self):
        """Inspect visually the graph, identify the connected
        components, call the method to compute them form graph
        and test if everything match.
        """
        self.graph.clear()
        self.graph.from_string(sample_gfa1)

        component1 = {'4'}
        component2 = {'12', '11', '13'}
        component3 = {'6', '2', '1', '3', '5'}

        components = list(pygfa.nodes_connected_components(self.graph))
        self.assertTrue(component1 in components)
        self.assertTrue(component2 in components)
        self.assertTrue(component3 in components)
            
    # :TODO: move test method
    def test_neighborhood_operation(self):
        self.graph.clear()
        self.graph.from_string(sample_gfa1)

        neighbors_ = self.graph.neighbors("2")
        self.assertTrue("6" in neighbors_)
        self.assertTrue("1" in neighbors_)
        self.assertTrue("5" not in neighbors_)

        with self.assertRaises(gfa.GFAError):
            self.graph.neighbors("42")

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

        result = self.graph.search(lambda element: \
                                       element["from_node"] == "1",\
                                       limit_type=gfa.Element.EDGE)
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

        result = self.graph.search(lambda element: \
                                       "xx" in element,\
                                       limit_type=gfa.Element.SUBGRAPH)
        self.assertTrue("15" in result)
        self.assertTrue(len(result) == 1)

        greater_than_comparator = lambda element: int(element['slen']) >= 140
        result = self.graph.search(greater_than_comparator,
                                    limit_type=gfa.Element.NODE)
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
        different_node.node("3")['sequence'] += "ACGT"
        self.assertFalse(self.graph == different_node)

        # Make end nodes sequence empty and check if
        # virtuals comparison works
        different_edge = copy.deepcopy(another_equal_graph)
        different_edge.node("1")["sequence"] = "*"
        different_edge.node("2")["sequence"] = "*"
        edge_ = different_edge.edge("1_to_2")
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
        


if  __name__ == '__main__':
    unittest.main()
