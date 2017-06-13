import sys
sys.path.insert(0, '../pygfa')

from parser.lines import header, segment, link, path, containment, fragment, edge, gap, group
from parser import error, line, field_validator as fv
from graph_element import node, edge as ge
import gfa
import re
import unittest

class TestLine (unittest.TestCase):

    graph = gfa.GFA ()
    
    def test_add_node (self):
        self.graph.clear ()
        
        seg = segment.SegmentV1.from_string ("S\t3\tTGCAACGTATAGACTTGTCAC\tRC:i:4\tui:Z:test\tab:Z:another_test")
        nod = node.Node.from_line (seg)
        self.graph.add_node (nod)

        print ("\nNODES:\n{0}".format (self.graph.nodes(data=True)))
        self.assertTrue (len (self.graph.nodes ()) == 1)
        self.assertTrue (self.graph.node['3']['sequence'] == "TGCAACGTATAGACTTGTCAC")
        self.assertTrue (self.graph.node['3']['id'] == "3")
        self.assertTrue (self.graph.node['3']['opt_fields']['ui'].value == "test")
        self.assertTrue (self.graph.node['3']['opt_fields']['ui'].type == "Z")


    def test_add_edge (self):
        self.graph.clear ()
        
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

        print (self.graph.edge)

        
        print ("NODES:\n{0}".format (self.graph.nodes (data=True)))
        print ("\nEDGES:\n{0}".format (self.graph.edges(data=True)))

        self.assertTrue (len (self.graph.edge['3']['4']) == 2)

        # a virtual id is given to F and L
        print ("\nEDGES BETWEEN 3 AND 4\n{0}".format (self.graph.edge['3']['4']))
        self.assertTrue (len (self.graph.nodes ()) == 2)

        # The F line is added first so it will have id 'virtual_0'
        self.assertTrue (self.graph.edge['3']['4']['virtual_0']['from_node'] == "3")
        
        


if  __name__ == '__main__':
    unittest.main()
