import sys
sys.path.insert(0, '../pygfa')

from parser.lines import header, segment, link, path, containment, fragment, edge, gap, group
from parser import error, line, field_validator as fv
from graph_element import node, edge as ge, subgraph as sg
import gfa
import unittest

class TestLine (unittest.TestCase):

    graph = gfa.GFA ()
    
    def test_add_node (self):
        self.graph.clear ()
        print ("\n-------------------------TEST ADD NODE-------------------------\n")
        
        seg = segment.SegmentV1.from_string ("S\t3\tTGCAACGTATAGACTTGTCAC\tRC:i:4\tui:Z:test\tab:Z:another_test")
        nod = node.Node.from_line (seg)
        self.graph.add_node (nod)

        print ("\nNODES:\n{0}".format (self.graph.nodes(data=True)))
        self.assertTrue (len (self.graph.nodes ()) == 1)
        self.assertTrue (self.graph.get_node('3')['sequence'] == "TGCAACGTATAGACTTGTCAC")
        self.assertTrue (self.graph.get_node('3')['nid'] == "3")
        self.assertTrue (self.graph.get_node('3')['ui'].value == "test")
        self.assertTrue (self.graph.get_node('3')['ui'].type == "Z")


    def test_add_edge (self):
        self.graph.clear ()
        print ("\n-------------------------TEST ADD EDGE-------------------------\n")
        
        seg = segment.SegmentV1.from_string ("S\t3\tTGCAACGTATAGACTTGTCAC\tRC:i:4\tui:Z:test\tab:Z:another_test")
        nod = node.Node.from_line (seg)
        self.graph.add_node (nod)
        
        seg = segment.SegmentV1.from_string ("S\t4\tTGCAACGTATAGACTTGTCAC\tRC:i:4\tui:Z:test\tab:Z:another_test")
        nod = node.Node.from_line (seg)
        self.graph.add_node (nod)

        line = fragment.Fragment.from_string ("F\t3\t4-\t0\t140$\t0\t140\t11M")
        edg = ge.Edge.from_line (line)
        self.graph.add_edge (edg)

        line = link.Link.from_string ("L\t3\t+\t4\t-\t47M\tui:Z:test\tab:Z:another_test")
        edg = ge.Edge.from_line (line)
        self.graph.add_edge (edg)

        print (self.graph.get_edge('*'))

        
        print (self.graph.pprint())
        self.assertTrue (len (self.graph.get_edge(('3', '4'))) == 2)

        # a virtual id is given to F and L
        print ("\nEDGES BETWEEN 3 AND 4\n{0}".format (self.graph.get_edge(('3','4'))))
        self.assertTrue (len (self.graph.nodes ()) == 2)

        # The F line is added first so it will have id 'virtual_0'
        # This first test get all the edges between node 3 and 4 and the get the edge labelled 'virtual_0'
        self.assertTrue (self.graph.get_edge(('3','4'))['virtual_0']['from_node'] == "3")

        # This test instead get instantly the edge labelled 'virtual_0', that is unique
        # in the graph
        self.assertTrue (self.graph.get_edge('virtual_0')['from_node'] == "3")

        # The default behaviour of get_edge is to call edge on the graph, so
        # it returns all the edges in the graph
        self.assertTrue (len (self.graph.get_edge ()) == 2)
        print (self.graph.pprint())


    def test_subgraphs (self):
        self.graph.clear ()
        print ("\n-------------------------TEST SUBGRAPHS-------------------------\n")
        line = path.Path.from_string ("P\t14\t11+,12+\t122M\tui:Z:test\tab:Z:another_test")
        sb = sg.Subgraph.from_line (line)
        self.graph.add_subgraph (sb)

        line = group.OGroup.from_string ("O\t15\t11+ 11_to_13+ 13+\txx:i:-1")
        sb = sg.Subgraph.from_line (line)
        self.graph.add_subgraph (sb)
        
        line = group.UGroup.from_string ("U\t16sub\t2 3\txx:i:-1")
        sb = sg.Subgraph.from_line (line)
        self.graph.add_subgraph (sb)

        print (self.graph.pprint())


    def test_as_graph_element (self):

        self.graph.clear ()

        print ("\n-------------------------TEST AS GRAPH ELEMENTS-------------------------\n")
        seg = segment.SegmentV1.from_string ("S\t3\tTGCAACGTATAGACTTGTCAC\tRC:i:4\tui:Z:test\tab:Z:another_test")
        nod1 = node.Node.from_line (seg)
        self.graph.add_node (nod1)

        seg = segment.SegmentV1.from_string ("S\t4\tTGCAACGTATAGACTTGTCAC\tRC:i:4\tui:Z:test\tab:Z:another_test")
        nod = node.Node.from_line (seg)
        self.graph.add_node (nod)
        
        line = fragment.Fragment.from_string ("F\t3\t4-\t0\t140$\t0\t140\t11M")
        edg = ge.Edge.from_line (line)
        self.graph.add_edge (edg)

        self.assertTrue (self.graph.as_graph_element ('3') == nod1)
        self.assertTrue (self.graph.as_graph_element ('virtual_0') == edg)


    def test_get_subgraph (self):
        print ("\n-------------------------TEST GET SUBGRAPH-------------------------\n")
        seg = segment.SegmentV1.from_string("S\t13\t*")
        nod = node.Node.from_line (seg)
        self.graph.add_node (nod)

        seg = segment.SegmentV1.from_string("S\t11\t*")
        nod = node.Node.from_line (seg)
        self.graph.add_node (nod)

        line = edge.Edge.from_string ("E\t16_to_12\t11+\t12+\t18\t140$\t0\t122\t122M")
        edg = ge.Edge.from_line (line)
        self.graph.add_edge (edg)

        p = path.Path.from_string("P\t15\t11+,16_to_12,13+\t120M")
        sb = sg.Subgraph.from_line (p)
        self.graph.add_subgraph (sb)

        print (self.graph.get_subgraph('15').pprint() )
        


if  __name__ == '__main__':
    unittest.main()
