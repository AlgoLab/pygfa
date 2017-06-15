import sys
sys.path.insert(0, '../pygfa')

from graph_element import node, edge as graph_edge, subgraph
from parser.lines import header, segment, link, path, containment, fragment, edge, gap, group
from parser import line

import unittest

class TestGraphElement (unittest.TestCase):

    def test_node (self):
        nod = node.Node ("15", "acgt", 4)
        with self.assertRaises (node.InvalidNodeError):
            nod = node.Node ("*", "3", "aCGT")

        correct_segment = segment.SegmentV1 ()
        correct_segment.add_field (line.Field ('name', "3"))
        correct_segment.add_field (line.Field ('sequence', "TGCAACGTATAGACTTGTCAC"))
        self.assertTrue (correct_segment.is_valid ())

        try:
            node.Node.from_line (correct_segment)
        except Exception as e:
            self.fail (e)
        
        fault_segment = segment.SegmentV1 ()
        fault_segment.add_field (line.Field ('name', "3"))
        # By not adding this, the segment hasn't got all the field required
        # fault_segment.add_field (line.Field ('sequence', "TGCAACGTATAGACTTGTCAC"))
        self.assertFalse (fault_segment.is_valid ())

        with self.assertRaises (node.InvalidNodeError):
            node.Node.from_line (fault_segment)
        

    
    def test_node_from_segment (self):
        seg = segment.SegmentV1.from_string ("S\t3\tTGCAACGTATAGACTTGTCAC\tRC:i:4")
        nod = node.Node.from_line (seg)
        self.assertTrue (nod.nid == seg.fields['name'].value)
        self.assertTrue (nod.slen == None)
        self.assertTrue (nod.sequence == seg.fields['sequence'].value)
        self.assertTrue (nod.opt_fields['RC'].value == seg.fields['RC'].value)
        
        seg = segment.SegmentV2.from_string ("S\t3\t21\tTGCAACGTATAGACTTGTCAC\tRC:i:4")
        nod = node.Node.from_line (seg)

        self.assertTrue (nod.nid == seg.fields['sid'].value)
        self.assertTrue (nod.slen == seg.fields['slen'].value)
        self.assertTrue (nod.sequence == seg.fields['sequence'].value)
        self.assertTrue (nod.opt_fields['RC'].value == seg.fields['RC'].value)

        
    def test_edge_from_link (self):
        line = link.Link.from_string ("L\t3\t+\t65\t-\t47M\tui:Z:test\tab:Z:another_test")
        ed = graph_edge.Edge.from_line (line)

        self.assertTrue (ed.eid == "*")
        self.assertTrue (ed.from_node == line.fields['from'].value + line.fields['from_orn'].value)
        self.assertTrue (ed.to_node == line.fields['to'].value + line.fields['to_orn'].value)
        self.assertTrue (ed.from_positions == (None, None))
        self.assertTrue (ed.to_positions == (None, None))
        self.assertTrue (ed.alignment == line.fields['overlap'].value)
        self.assertTrue (len (ed.opt_fields) == 2)
        self.assertTrue (ed.opt_fields['ui'] == line.fields['ui'])
        self.assertTrue (ed.opt_fields['ui'].value == "test")
        self.assertTrue (ed.opt_fields['ab'].value == "another_test")


    def test_edge_from_containment (self):
        line = containment.Containment.from_string ("C\ta\t+\tb\t-\t10\t*\tui:Z:test\tab:Z:another_test")
        ed = graph_edge.Edge.from_line (line)

        self.assertTrue (ed.eid == "*")
        self.assertTrue (ed.from_node == line.fields['from'].value + line.fields['from_orn'].value)
        self.assertTrue (ed.to_node == line.fields['to'].value + line.fields['to_orn'].value)
        self.assertTrue (ed.from_positions == (None, None))
        self.assertTrue (ed.to_positions == (None, None))
        self.assertTrue (ed.alignment == line.fields['overlap'].value)
        self.assertTrue (len (ed.opt_fields) == 3)
        self.assertTrue (ed.opt_fields['pos'] == line.fields['pos'])
        self.assertTrue (ed.opt_fields['ui'] == line.fields['ui'])
        self.assertTrue (ed.opt_fields['ui'].value == "test")
        self.assertTrue (ed.opt_fields['ab'].value == "another_test")
    
        
    def test_edge_from_fragment (self):
        line = fragment.Fragment.from_string ("F\t12\t2-\t0\t140$\t0\t140\t11M\tui:Z:test\tab:Z:another_test")
        ed = graph_edge.Edge.from_line (line)

        self.assertTrue (ed.eid == None)
        self.assertTrue (ed.from_node == line.fields['sid'].value)
        self.assertTrue (ed.to_node == line.fields['external'].value)
        self.assertTrue (ed.from_positions == (line.fields['sbeg'].value, line.fields['send'].value))
        self.assertTrue (ed.to_positions == (line.fields['fbeg'].value, line.fields['fend'].value))
        self.assertTrue (ed.alignment == line.fields['alignment'].value)
        self.assertTrue (len (ed.opt_fields) == 2)
        self.assertTrue (ed.opt_fields['ui'] == line.fields['ui'])
        self.assertTrue (ed.opt_fields['ui'].value == "test")
        self.assertTrue (ed.opt_fields['ab'].value == "another_test")


    def test_edge_from_edge (self):
        line = edge.Edge.from_string ("E\t*\t23-\t16+\t0\t11\t0\t11\t11M\tui:Z:test\tab:Z:another_test")
        ed = graph_edge.Edge.from_line (line)

        self.assertTrue (ed.eid == line.fields['eid'].value)
        self.assertTrue (ed.from_node == line.fields['sid1'].value)
        self.assertTrue (ed.to_node == line.fields['sid2'].value)
        self.assertTrue (ed.from_positions == (line.fields['beg1'].value, line.fields['end1'].value))
        self.assertTrue (ed.to_positions == (line.fields['beg2'].value, line.fields['end2'].value))
        self.assertTrue (ed.alignment == line.fields['alignment'].value)
        self.assertTrue (len (ed.opt_fields) == 2)
        self.assertTrue (ed.opt_fields['ui'] == line.fields['ui'])
        self.assertTrue (ed.opt_fields['ui'].value == "test")
        self.assertTrue (ed.opt_fields['ab'].value == "another_test")

        
    def test_edge_from_gap (self):
        line = gap.Gap.from_string ("G\tg\tA+\tB-\t1000\t*\tui:Z:test\tab:Z:another_test")
        ed = graph_edge.Edge.from_line (line)

        self.assertTrue (ed.eid == line.fields['gid'].value)
        self.assertTrue (ed.from_node == line.fields['sid1'].value)
        self.assertTrue (ed.to_node == line.fields['sid2'].value)
        self.assertTrue (len (ed.opt_fields) == 2)

        self.assertTrue (ed.displacement == "1000")
        self.assertTrue (ed.variance == "*")
                             
        self.assertTrue (ed.opt_fields['ui'].value == "test")
        self.assertTrue (ed.opt_fields['ab'].value == "another_test")


    def test_subgraph_from_path (self):
        line = path.Path.from_string ("P\t14\t11+,12+\t122M\tui:Z:test\tab:Z:another_test")
        sb = subgraph.Subgraph.from_line (line)

        self.assertTrue (sb.sub_id == line.fields['path_name'].value)
        self.assertTrue (sb.elements == line.fields['seqs_names'].value)
        self.assertTrue (sb.opt_fields['overlaps'].value == line.fields['overlaps'].value)


    def test_subgraph_from_ogroup (self):
        line = group.OGroup.from_string ("O\t15\t11+ 11_to_13+ 13+\txx:i:-1")
        sb = subgraph.Subgraph.from_line (line)

        self.assertTrue (sb.sub_id == line.fields['oid'].value)
        self.assertTrue (sb.elements == line.fields['references'].value)
        self.assertTrue (sb.opt_fields['xx'].value == line.fields['xx'].value)

        
    def test_subgraph_from_ugroup (self):
        line = group.UGroup.from_string ("U\t16sub\t2 3\txx:i:-1")
        sb = subgraph.Subgraph.from_line (line)

        self.assertTrue (sb.sub_id == line.fields['uid'].value)
        self.assertTrue (sb.elements == line.fields['references'].value)
        self.assertTrue (sb.opt_fields['xx'].value == line.fields['xx'].value)


        
        
if  __name__ == '__main__':
    unittest.main()
    
