import copy
import re
import sys
import unittest

sys.path.insert(0, "../")

from pygfa.graph_element import node, edge as graph_edge, subgraph
from pygfa.graph_element.parser import segment, link, path, containment, line


class BadNode:
    """A class that mimic the Node class."""

    def __init__(self, nid, sequence, slen, opt_fields):
        self.nid = nid
        self.sequence = sequence
        self.slen = slen
        self.opt_fields = copy.deepcopy(opt_fields)


class BadEdge:
    """A class that mimic the Edge class."""

    def __init__(
        self,
        eid,
        from_node,
        from_orn,
        to_node,
        to_orn,
        from_positions,
        to_positions,
        alignment,
        distance,
        variance,
        opt_fields,
    ):
        self.eid = eid
        self.from_node = from_node
        self.from_orn = from_orn
        self.to_node = to_node
        self.to_orn = to_orn
        self.from_positions = copy.deepcopy(from_positions)
        self.to_positions = copy.deepcopy(to_positions)
        self.alignment = alignment
        self.distance = distance
        self.variance = variance
        self.opt_fields = copy.deepcopy(opt_fields)


class BadSubgraph:
    """A class that mimic the Subgraph class"""

    def __init__(self, sub_id, elements, opt_fields):
        self.sub_id = sub_id
        self.elements = copy.deepcopy(elements)
        self.opt_fields = copy.deepcopy(opt_fields)


class CustomLine(line.Line):
    """A custom line."""

    def __init__(self):
        super().__init__("R")

    @classmethod
    def from_string(self, string):
        fields = re.split("\t", string)

        custom = CustomLine()
        for field in fields:
            custom._fields[field] = field
        return custom


class TestGraphElement(unittest.TestCase):
    def test_node(self):
        _ = node.Node("15", "acgt", 4)
        with self.assertRaises(node.InvalidNodeError):
            _ = node.Node("*", "3", "aCGT")

        correct_segment = segment.SegmentV1()
        correct_segment.add_field(line.Field("name", "3"))
        correct_segment.add_field(line.Field("sequence", "TGCAACGTATAGACTTGTCAC"))
        correct_segment.add_field(line.OptField("AA", "test", "Z"))
        correct_segment.add_field(line.OptField("AB", "test2", "Z"))
        self.assertTrue(segment.SegmentV1.is_valid(correct_segment))

        node_ = node.Node.from_line(correct_segment)

        self.assertTrue(node.is_node(node_))

        bad_node = BadNode(node_.nid, node_.sequence, node_.slen, node_.opt_fields)
        self.assertTrue(node.is_node(bad_node))
        self.assertTrue(bad_node == node_)

        # if all the opt_fields of the left operand are not
        # in the opt_fields of the right operand the
        # nodes are not equal
        del bad_node.opt_fields["AA"]
        self.assertFalse(bad_node == node_)

        bad_node.nid = "5"
        self.assertFalse(bad_node == node_)

        del bad_node.nid
        self.assertFalse(node.is_node(bad_node))
        self.assertTrue(bad_node != node_)
        # self.assertTrue(str(node_) == "nid : 3,\t" \
        #                                       + "sequence : TGCAACGTATAGACTTGTCAC,\t" \
        #                                       + "slen : None,\t" \
        #                                       + "opt_fields : []")

        fault_segment = segment.SegmentV1()
        fault_segment.add_field(line.Field("name", "3"))
        # By not adding this, the segment hasn't got all the field required
        self.assertFalse(segment.SegmentV1.is_valid(fault_segment))

        fault_line = segment.SegmentV1()
        fault_line._fields["name_"] = line.Field("name", "3")
        fault_line._fields["sequence"] = line.Field("sequence", "TGCAACGTATAGACTTGTCAC")
        with self.assertRaises(line.InvalidLineError):
            node.Node.from_line(fault_line)

        # inserting a wrong field to opt_fields
        seg = segment.SegmentV1.from_string("S\t3\t21\tTGCAACGTATAGACTTGTCAC\tRC:i:4")
        seg.fields["wrong_field"] = 42
        self.assertTrue("wrong_field" in seg.fields)
        node_ = node.Node.from_line(seg)
        self.assertFalse("wrong_field" in node_.opt_fields)

        with self.assertRaises(node.InvalidNodeError):
            node.Node("3", 3, "acgt")

        with self.assertRaises(node.InvalidNodeError):
            node.Node("3", "3", "acgt acgt")

    def test_edge(self):
        # Test with Link line instead of GFA2 Edge line
        edge_ = graph_edge.Edge.from_line(link.Link.from_string("L\t23\t-\t16\t+\t11M\tui:Z:test\tab:Z:another_test"))
        self.assertTrue(graph_edge.is_edge(edge_))

        # add an invalid OptField to the opt_fields dictionary and check
        # that the Edge init just ignores it.
        edge_._opt_fields["not_valid"] = 42
        self.assertTrue("not_valid" in edge_.opt_fields)
        new_edge = graph_edge.Edge(
            edge_.eid,
            edge_.from_node,
            edge_.from_orn,
            edge_.to_node,
            edge_.to_orn,
            edge_.from_positions,
            edge_.to_positions,
            edge_.alignment,
            edge_.distance,
            edge_.variance,
            edge_.opt_fields,
        )
        self.assertFalse("not_valid" in new_edge.opt_fields)

        # check duck typing
        bad_edge = BadEdge(
            edge_.eid,
            edge_.from_node,
            edge_.from_orn,
            edge_.to_node,
            edge_.to_orn,
            edge_.from_positions,
            edge_.to_positions,
            edge_.alignment,
            edge_.distance,
            edge_.variance,
            edge_.opt_fields,
        )
        self.assertTrue(bad_edge == edge_)
        self.assertTrue(graph_edge.is_edge(bad_edge))

        bad_edge.from_node = "42"
        self.assertFalse(edge_ == bad_edge)

        # insert the correct from_node back
        bad_edge.from_node = edge_.from_node
        del bad_edge.opt_fields["ab"]
        self.assertFalse(edge_ == bad_edge)

        # insert the opt field previously deleted
        bad_edge.opt_fields["ab"] = copy.deepcopy(edge_.opt_fields["ab"])
        del bad_edge.from_node
        self.assertFalse(graph_edge.is_edge(bad_edge))
        self.assertTrue(bad_edge != edge_)

        # check tuple length in Edge init
        with self.assertRaises(graph_edge.InvalidEdgeError):
            bad_edge = graph_edge.Edge(
                edge_.eid,
                edge_.from_node,
                edge_.from_orn,
                edge_.to_node,
                edge_.to_orn,
                ("42", "42", "42"),
                edge_.to_positions,
                edge_.alignment,
                edge_.distance,
                edge_.variance,
                edge_.opt_fields,
            )

        with self.assertRaises(graph_edge.InvalidEdgeError):
            bad_edge = graph_edge.Edge(
                edge_.eid,
                edge_.from_node,
                edge_.from_orn,
                edge_.to_node,
                edge_.to_orn,
                edge_.from_positions,
                ("42", "42", "42"),
                edge_.alignment,
                edge_.distance,
                edge_.variance,
                edge_.opt_fields,
            )

        # if line cannot be converted to an Edge object just return None
        custom_line = CustomLine.from_string("R\ta\tcustom\tline")
        self.assertTrue(graph_edge.Edge.from_line(custom_line) is None)

        # check raising exceptions if line hasn't the correct fields.
        custom_line._type = "E"
        with self.assertRaises(line.InvalidLineError):
            graph_edge.Edge.from_line(custom_line)

    def test_subgraph(self):
        path_ = path.Path.from_string("P\t14\t11+,12+\t122M\tui:Z:test\tab:Z:another_test")
        sb = subgraph.Subgraph.from_line(path_)
        self.assertTrue(subgraph.is_subgraph(sb))

        # check duck typing for subgraph
        bad_graph = BadSubgraph(sb.sub_id, sb.elements, sb.opt_fields)
        self.assertTrue(subgraph.is_subgraph(bad_graph))
        # check for equality
        self.assertTrue(bad_graph == sb)

        del bad_graph.sub_id
        self.assertFalse(subgraph.is_subgraph(bad_graph))
        # check for unequality
        self.assertTrue(bad_graph != sb)
        bad_graph.sub_id = sb.sub_id  # restore previous state
        del bad_graph.opt_fields["ui"]
        self.assertTrue(bad_graph != sb)
        bad_graph.opt_fields["ui"] = sb.opt_fields["ui"]  # restore previous state
        bad_graph.sub_id = "42"
        self.assertTrue(bad_graph != sb)
        bad_graph.sub_id = sb.sub_id  # restore previous state

        # check for init exceptions
        with self.assertRaises(subgraph.InvalidSubgraphError):
            subgraph.Subgraph(42, sb.elements, sb.opt_fields)

        with self.assertRaises(subgraph.InvalidSubgraphError):
            subgraph.Subgraph(sb.sub_id, 42, sb.opt_fields)

        # insert an invalid OptField and check it won't be added
        sb._opt_fields["AA"] = 42
        sb_ = subgraph.Subgraph(sb.sub_id, sb.elements, sb.opt_fields)
        self.assertFalse("AA" in sb_.opt_fields)

        # check unexpected line type in from_line
        custom_line = CustomLine.from_string("R\ta\tcustom\tline")
        self.assertTrue(subgraph.Subgraph.from_line(custom_line) is None)

        # check exception in from_line
        custom_line._type = "P"
        with self.assertRaises(line.InvalidLineError):
            subgraph.Subgraph.from_line(custom_line)

        subgraph_dict = sb.as_dict()
        self.assertTrue(subgraph_dict["sub_id"] == sb.sub_id)
        self.assertTrue(subgraph_dict["elements"] == sb.elements)
        self.assertTrue(subgraph_dict["ab"] == sb.opt_fields["ab"])

    def test_node_from_segment(self):
        seg = segment.SegmentV1.from_string("S\t3\tTGCAACGTATAGACTTGTCAC\tRC:i:4")
        node_ = node.Node.from_line(seg)
        self.assertTrue(node_.nid == seg.fields["name"].value)
        self.assertTrue(node_.slen == len(seg.fields["sequence"].value))
        self.assertTrue(node_.sequence == seg.fields["sequence"].value)
        self.assertTrue(node_.opt_fields["RC"].value == seg.fields["RC"].value)

        seg = segment.SegmentV2.from_string("S\t3\t21\tTGCAACGTATAGACTTGTCAC\tRC:i:4")
        node_ = node.Node.from_line(seg)

        self.assertTrue(node_.nid == seg.fields["sid"].value)
        self.assertTrue(node_.slen == seg.fields["slen"].value)
        self.assertTrue(node_.sequence == seg.fields["sequence"].value)
        self.assertTrue(node_.opt_fields["RC"].value == seg.fields["RC"].value)

    def test_edge_from_link(self):
        line = link.Link.from_string("L\t3\t+\t65\t-\t47M\tui:Z:test\tab:Z:another_test")
        ed = graph_edge.Edge.from_line(line)
        self.assertTrue(ed.eid == "*")
        self.assertTrue(ed.from_node == line.fields["from"].value)
        self.assertTrue(ed.from_orn == line.fields["from_orn"].value)
        self.assertTrue(ed.to_node == line.fields["to"].value)
        self.assertTrue(ed.to_orn == line.fields["to_orn"].value)
        self.assertTrue(ed.from_positions == (None, None))
        self.assertTrue(ed.to_positions == (None, None))
        self.assertTrue(ed.alignment == line.fields["overlap"].value)
        self.assertTrue(len(ed.opt_fields) == 2)
        self.assertTrue(ed.opt_fields["ui"] == line.fields["ui"])
        self.assertTrue(ed.opt_fields["ui"].value == "test")
        self.assertTrue(ed.opt_fields["ab"].value == "another_test")

        line = link.Link.from_string("L\t3\t+\t65\t-\t47M\tui:Z:test\tab:Z:another_test\tID:Z:3_to_65")
        ed = graph_edge.Edge.from_line(line)
        self.assertTrue(ed.eid == "3_to_65")

    def test_edge_from_containment(self):
        line = containment.Containment.from_string("C\ta\t+\tb\t-\t10\t*\tui:Z:test\tab:Z:another_test")
        ed = graph_edge.Edge.from_line(line)
        self.assertTrue(ed.eid == "*")
        self.assertTrue(ed.from_node == line.fields["from"].value)
        self.assertTrue(ed.from_orn == line.fields["from_orn"].value)
        self.assertTrue(ed.to_node == line.fields["to"].value)
        self.assertTrue(ed.to_orn == line.fields["to_orn"].value)
        self.assertTrue(ed.from_positions == (None, None))
        self.assertTrue(ed.to_positions == (None, None))
        self.assertTrue(ed.alignment == line.fields["overlap"].value)
        self.assertTrue(len(ed.opt_fields) == 3)
        self.assertTrue(ed.opt_fields["pos"] == line.fields["pos"])
        self.assertTrue(ed.opt_fields["ui"] == line.fields["ui"])
        self.assertTrue(ed.opt_fields["ui"].value == "test")
        self.assertTrue(ed.opt_fields["ab"].value == "another_test")

        line = containment.Containment.from_string("C\ta\t+\tb\t-\t10\t*\tui:Z:test\tab:Z:another_test\tID:Z:a_to_b")
        ed = graph_edge.Edge.from_line(line)
        self.assertTrue(ed.eid == "a_to_b")

    # GFA2 module tests - all skipped since modules were removed
    @unittest.skip("GFA2 fragment module removed")
    def test_edge_from_fragment(self):
        pass

    @unittest.skip("GFA2 edge module removed")
    def test_edge_from_edge(self):
        pass

    @unittest.skip("GFA2 gap module removed")
    def test_edge_from_gap(self):
        pass

    def test_subgraph_from_path(self):
        line = path.Path.from_string("P\t14\t11+,12+\t122M\tui:Z:test\tab:Z:another_test")
        sb = subgraph.Subgraph.from_line(line)

        self.assertTrue(sb.sub_id == line.fields["path_name"].value)
        self.assertTrue([u + v for u, v in sb.elements.items()] == line.fields["seqs_names"].value)
        self.assertTrue(sb.opt_fields["overlaps"].value == line.fields["overlaps"].value)

    @unittest.skip("GFA2 group module removed")
    def test_subgraph_from_ogroup(self):
        pass

    @unittest.skip("GFA2 group module removed")
    def test_subgraph_from_ugroup(self):
        pass


if __name__ == "__main__":
    unittest.main()
