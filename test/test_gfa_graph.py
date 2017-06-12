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
        self.graph._graph.clear ()
        
        seg = segment.SegmentV1.from_string ("S\t3\tTGCAACGTATAGACTTGTCAC\tRC:i:4")
        nod = node.Node.from_line (seg)
        self.graph.add_node (nod)

        print (self.graph.nodes (data=True))
        self.assertTrue (len (self.graph.nodes (data=True)) == 1)
        self.assertTrue (self.graph.node['3']['sequence'] == "TGCAACGTATAGACTTGTCAC")
        self.assertTrue (self.graph.node['3']['id'] == "3")


    def test_add_edge (self):
        self.graph._graph.clear ()
        
        seg = segment.SegmentV1.from_string ("S\t3\tTGCAACGTATAGACTTGTCAC\tRC:i:4")
        nod = node.Node.from_line (seg)
        self.graph.add_node (nod)
        
        seg = segment.SegmentV1.from_string ("S\t4\tTGCAACGTATAGACTTGTCAC\tRC:i:4")
        nod = node.Node.from_line (seg)
        self.graph.add_node (nod)

        line = fragment.Fragment.from_string ("F\t3\t4-\t0\t140$\t0\t140\t11M")
        edg = ge.Edge.from_line (line)
        self.graph.add_edge (edg)

        self.assertTrue (len (self.graph.nodes (data=True)) == 2)
        
        


if  __name__ == '__main__':
    unittest.main()
