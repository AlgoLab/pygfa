import sys
sys.path.insert(0, '../')

import re
import unittest
import copy

from pygfa.graph_element.parser import header, segment, link, path, containment, fragment, edge, gap, group
from pygfa.graph_element.parser import line, field_validator as fv

# Tips: How to TDD with regex
# https://stackoverflow.com/questions/488601/ (continue...)
# how-do-you-unit-test-regular-expressions


class TestField():
    """
    A test class that is similar to optfield, but without name
    attribute and allows to have any type of field listed in
    field_validator dictionary of types.

    It's just a custom class to easily check the different types of fields.
    If a TestField object can be initialized, the value respects its field type.
    """
    def __init__(self, value, field_type):
        self.type = field_type
        self.value = fv.validate(value, field_type)


class BadField():
    """
    A class that mimic the Field and OptField status.
    """
    def __init__(self, name=None, value=None, type_=None):
        self.name = name
        self.type = type_
        self.value = value


        

class TestLine(unittest.TestCase):


    def test_field_validator(self):
        """Test the field validator methods.
        The different types a datatype can assume are tested in
        other methods.
        """
        self.assertTrue(fv.is_valid("3", fv.TYPE_i))
        with self.assertRaises(fv.FormatError):
            fv.is_valid(3, fv.TYPE_i)
        with self.assertRaises(fv.UnknownDataTypeError):
            fv.is_valid("3", "a custom datatype")

    
    def test_field_type(self):
        """Use TestField to check how the different field data types
        are managed.

        TODO:
            Check for json parser/verifier existence within python
            (should exists).
        """
        with self.assertRaises(fv.UnknownDataTypeError):
            optf = TestField('bb', 'c') # c is an invalid type of field

        optf = TestField('A', 'A')
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('aa', 'A')
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('', 'A')
        
        optf = TestField('-42', 'i')
        self.assertTrue(optf.value == -42)
        optf = TestField('+42', 'i')
        optf = TestField('42', 'i')
        self.assertTrue(optf.value == +42)
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('aa', 'i')
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('', 'i')

        optf = TestField('-1.4241e-11', 'f')
        optf = TestField('+1.4241E+11', 'f')
        optf = TestField('42', 'f')
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('A', 'f')
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('042e0.5', 'f')
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('', 'f')

        optf = TestField('The gray fox jumped from somewhere.', 'Z')
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('力 - is the force', 'Z')
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('\n - is the force', 'Z')
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('', 'Z')

        # this test should fail
        optf = TestField('The gray fox jumped from somewhere.', 'J')
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('力 - is the force', 'J')
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('\n - is the force', 'J')
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('', 'J')

        optf = TestField('A5F', 'H')
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('a5f', 'H')
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('g', 'H')
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('', 'H')

        optf = TestField('c,15,17,21,-32', 'B')
        optf = TestField('f,15,.05e4', 'B')
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('f15,i.05e4', 'B')
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('', 'B')

        optf = TestField('(12', fv.GFA1_NAME)
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('', fv.GFA1_NAME)

        optf = TestField('+', fv.GFA1_ORIENTATION)
        optf = TestField('-', fv.GFA1_ORIENTATION)
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('', fv.GFA1_ORIENTATION)
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('++', fv.GFA1_ORIENTATION)
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('a', fv.GFA1_ORIENTATION)
        
        optf = TestField('(12-,14+,17-', fv.GFA1_NAMES)

        # no sign orientation near 14
        optf = TestField('(12-,14,17-', fv.GFA1_NAMES)
        
        # space is not allowed
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('(12-, 14+,17-', fv.GFA1_NAMES)
        
        # even for separating elements in the array
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('', fv.GFA1_NAMES)

        optf = TestField('acgt', fv.GFA1_SEQUENCE)
        optf = TestField('*', fv.GFA1_SEQUENCE)
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('*acgt', fv.GFA1_SEQUENCE)
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('', fv.GFA1_SEQUENCE)

        optf = TestField('0', fv.GFA1_INT)
        optf = TestField('100', fv.GFA1_INT)
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('-1', fv.GFA1_INT)
        
        optf = TestField('*', fv.GFA1_CIGAR)
        optf = TestField('5I2M', fv.GFA1_CIGAR)
        self.assertTrue(fv.is_gfa1_cigar(optf.value))
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('', fv.GFA1_CIGAR)

        optf = TestField('*,*,*', fv.GFA1_CIGARS)
        optf = TestField('*', fv.GFA1_CIGARS)
        optf = TestField('5I2M,*,3X,22M', fv.GFA1_CIGARS)
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('', fv.GFA1_CIGARS)
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('5I2M,*,3,22M', fv.GFA1_CIGARS)

        optf = TestField('5I2M', fv.GFA2_CIGAR)
        self.assertTrue(fv.is_gfa2_cigar(optf.value))
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('', fv.GFA2_CIGAR)
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('*', fv.GFA2_CIGAR)
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('5I3X', fv.GFA2_CIGAR)

        optf = TestField('aa', fv.GFA2_ID)
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('', fv.GFA2_ID)
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('a a', fv.GFA2_ID)

        optf = TestField('aa', fv.GFA2_IDS)
        self.assertTrue(optf.value == ['aa'])
        optf = TestField('aa bb cc dd', fv.GFA2_IDS)
        self.assertTrue(optf.value == ['aa', 'bb', 'cc', 'dd'])
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('', fv.GFA2_IDS)
        # there are 2 spaces between the a and the b
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('a  b', fv.GFA2_IDS)

        optf = TestField('aa+', fv.GFA2_REFERENCE)
        optf = TestField('aa-', fv.GFA2_REFERENCE)
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('', fv.GFA2_REFERENCE)
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('aa', fv.GFA2_REFERENCE)

        optf = TestField('aa+', fv.GFA2_REFERENCES)
        self.assertTrue(optf.value == ['aa+'])
        optf = TestField('aa+ bb- cc+ dd-', fv.GFA2_REFERENCES)
        self.assertTrue(optf.value == ['aa+', 'bb-', 'cc+', 'dd-'])
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('', fv.GFA2_REFERENCES)
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('aa bb+', fv.GFA2_REFERENCES)

        optf = TestField('42', fv.GFA2_OPTIONAL_INT)
        self.assertTrue(optf.value == 42)
        optf = TestField('*', fv.GFA2_OPTIONAL_INT)
        self.assertTrue(optf.value == "*")

        optf = TestField('42', fv.GFA2_INT)
        self.assertTrue(optf.value == 42)
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('', fv.GFA2_INT)
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('-42', fv.GFA2_INT)

        optf = TestField('42', fv.GFA2_TRACE)
        optf = TestField('42,42', fv.GFA2_TRACE)
        optf = TestField('42,42,42', fv.GFA2_TRACE)
        dazz_trace = fv.validate(optf.value, fv.GFA2_TRACE)
        self.assertTrue(fv.is_dazzler_trace(dazz_trace))
        
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('', fv.GFA2_TRACE)
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('-42', fv.GFA2_TRACE)

        optf = TestField('42', fv.GFA2_POSITION)
        # fv.GFA2_POSITION will be validated and converted
        # to a string
        self.assertTrue(optf.value == "42")
        optf = TestField('42$', fv.GFA2_POSITION)
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('', fv.GFA2_POSITION)
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('$', fv.GFA2_POSITION)
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('1$$', fv.GFA2_POSITION)

        optf = TestField('*', fv.GFA2_SEQUENCE)
        optf = TestField('acgtACGTXYZ', fv.GFA2_SEQUENCE)
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('', fv.GFA2_SEQUENCE)

        optf = TestField('aa', fv.GFA2_OPTIONAL_ID)
        optf = TestField('*', fv.GFA2_OPTIONAL_ID)
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('', fv.GFA2_OPTIONAL_ID)
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('* ', fv.GFA2_OPTIONAL_ID)

        optf = TestField('42,42,42', fv.GFA2_ALIGNMENT)
        optf = TestField('*', fv.GFA2_ALIGNMENT)
        optf = TestField('2I3M', fv.GFA2_ALIGNMENT)
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('', fv.GFA2_ALIGNMENT)
        with self.assertRaises(fv.InvalidFieldError):
            optf = TestField('42,13M', fv.GFA2_ALIGNMENT)

        # Missing field type tests
        # 'pos' : "^[0-9]*$", # positive integer \
        # TODO: this way the empty string is allowed. could it be possibly a
        # mistake in the specification of GFA1? Ask for it.
        #
        # 'cmt' : ".*"


    def test_OptField(self):

        with self.assertRaises(ValueError):
            field = line.OptField.from_string("AA:BB:i:Z")

        with self.assertRaises(ValueError):
            field = line.OptField("aa", "test", "lbl")

        with self.assertRaises(ValueError):
            field = line.OptField("aaA", "test", "lbl")

        field = line.OptField("na", "test", "Z")
        bf = BadField("na", "test", "Z")
        self.assertTrue(field == bf)

        bf.type = "xxx"
        self.assertTrue(field != bf)

        del(bf.name)
        self.assertFalse(field == bf)


    def test_Field(self):
        field = line.Field('name', '25')
        bf = BadField('name', '25')
        self.assertTrue(field == bf)

        del(bf.name)
        self.assertFalse(field == bf)
        

    def test_invalid_line(self):
        """
        Create a GFA1 Segment line, add to it a name and
        an optional field.
        Since it misses a required field(sequence) it shouldn't
        be valid. 
        """
        seg = segment.SegmentV1()
        seg.add_field(line.Field('name', '3'))
        seg.add_field(line.OptField('AC', '3', 'i'))
        self.assertFalse(segment.SegmentV1.is_valid(seg))


    def test_is_field(self):
        """
        Test for field checker.
        Try to simulate an erroneus behaviour of a field.
        """ 
        bf = BadField()
        bf.name = "valid_name"
        bf.value = 'acgt'

        # bf is a valid field
        self.assertTrue(line.is_field(bf))

        bf.name = 42 # bf has a name which is not a string,
        # so bf is not a valid field
        self.assertFalse(line.is_field(bf))

        bf.value = None # now bf is not a valid field
        self.assertFalse(line.is_field(bf))



    def test_line(self):
        """Test the different behaviour of line
        objects.
        Compare the behaviors of add_field. 
        """
        seg = segment.SegmentV1()
        # add a required field
        seg.add_field(line.Field('name', '3'))
        self.assertTrue(seg.fields['name'].value == '3')
        # add an optional field
        seg.add_field(line.OptField('AA', '3', 'i'))
        self.assertTrue(seg.fields['AA'].value == 3)

        # add any object
        with self.assertRaises(fv.InvalidFieldError):
            seg.add_field(3)

        # add a field previously added 
        with self.assertRaises(ValueError):
            seg.add_field(line.OptField('AA', '3', 'i'))

        # add an invalid optfield
        with self.assertRaises(fv.InvalidFieldError):
            seg.add_field(line.OptField('AA', 'a', 'i'))

        # if a Field is passed, the method just remove
        # the value associated with the Field name
        seg_copy = copy.deepcopy(seg)
        seg.remove_field(line.Field('name', '4'))
        self.assertTrue('name' not in seg.fields)
        self.assertTrue(seg != seg_copy)
        
        seg.add_field(line.Field('name', '3'))
        # if a string is passed, remove the value associated
        # with name of the key given        
        seg.remove_field('name')
        self.assertTrue('name' not in seg.fields)

        seg_copy = copy.deepcopy(seg)
        seg.remove_field('non_existent_field')
        self.assertTrue(seg_copy == seg)

        fields_copy = copy.deepcopy(seg.fields)
        self.assertTrue(seg != fields_copy)

        segment_fields = segment.SegmentV1.get_static_fields()
        for field in ('name', 'sequence', 'LN', \
                      'RC', 'FC', 'KC', 'SH', 'UR'):
            self.assertTrue(field in segment_fields)

        invalid_segment = segment.SegmentV1()
        invalid_segment.add_field(line.Field("name", "3"))
        self.assertFalse(segment.SegmentV1.is_valid(invalid_segment))

        # test against duck typing.
        # So in the case the user is trying to replicate the line class
        # (maybe to extend it)
        invalid_segment = line.Line()
        del(invalid_segment._type)
        self.assertFalse(segment.SegmentV1.is_valid(invalid_segment))

        invalid_segment = line.Line()
        invalid_segment.add_field(line.Field("name", "3"))
        invalid_segment.add_field(line.Field("sequence", "acgt"))
        self.assertFalse(segment.SegmentV1.is_valid(invalid_segment))
        

            
    def test_header(self):
        with self.assertRaises(line.InvalidLineError):
            header.Header.from_string("    ")

        head = header.Header.from_string("VN:Z:1.0")
        self.assertTrue(head.type == "H")
        self.assertTrue(head.fields['VN'].value == "1.0")
        self.assertTrue(header.Header.is_valid(head))
        
        head = header.Header.from_string("H\tVN:Z:1.0")
        self.assertTrue(head.type == "H")
        self.assertTrue(head.fields['VN'].value == "1.0")
        self.assertTrue(header.Header.is_valid(head))
        

    def test_Segment(self):
        """Test the parsing of a S line either following the
        GFA1 and the GFA2 specifications.
        """
        with self.assertRaises(line.InvalidLineError):
            segment.SegmentV1.from_string("  ")
        with self.assertRaises(line.InvalidLineError):
            segment.SegmentV1.from_string("TGCAACGTATAGACTTGTCAC")
        with self.assertRaises(fv.InvalidFieldError):
            segment.SegmentV1.from_string("TGCAACGTATAGACTTGTCAC\tRC:i:4")

        seg = segment.SegmentV1.from_string("S\t3\tTGCAACGTATAGACTTGTCAC\tRC:i:4")
        self.assertTrue(seg.type == "S")
        self.assertTrue(seg.fields['name'].value == "3")
        self.assertTrue(seg.fields['sequence'].value  == "TGCAACGTATAGACTTGTCAC")
        self.assertTrue(seg.fields['RC'].value == 4)
        self.assertTrue(segment.SegmentV1.is_valid(seg))
        self.assertTrue(\
                segment.is_segmentv1("S\t3\tTGCAACGTATAGACTTGTCAC\tRC:i:4"))
        self.assertFalse(segment.is_segmentv1(""))
        self.assertTrue(segment.is_segmentv1(seg))
        self.assertFalse(segment.is_segmentv1("tab0\ttab1\tACGT"))
        
        # the function should just try to identify if the given object
        # probably is a GFA1 segment, the full check will be done
        # by another function/method if necessary
        self.assertTrue(segment.is_segmentv1("S\ttab1\tACGT"))

        with self.assertRaises(line.InvalidLineError):
            segment.SegmentV2.from_string("  ")
        with self.assertRaises(line.InvalidLineError):
            segment.SegmentV2.from_string("t3\tTGCAACGTATAGACTTG")
        with self.assertRaises(fv.InvalidFieldError):
            segment.SegmentV2.from_string("t21\tTGCAACGTATAGACTTGTCAC\tRC:i:4")
            
        seg = segment.SegmentV2.from_string("S\t3\t21\tTGCAACGTATAGACTTGTCAC\tRC:i:4")
        self.assertTrue(seg.type == "S")
        self.assertTrue(seg.fields['sid'].value == "3")
        self.assertTrue(seg.fields['slen'].value == 21)
        self.assertTrue(seg.fields['sequence'].value  == "TGCAACGTATAGACTTGTCAC")
        self.assertTrue(seg.fields['RC'].value == 4)
        self.assertTrue(segment.SegmentV2.is_valid(seg))
        self.assertFalse(segment.is_segmentv2(""))
        self.assertTrue(segment.is_segmentv2(seg))
        self.assertFalse(segment.is_segmentv2("tab0\ttab1\t21\tACGT"))
        # the same proposition above for the GFA1 is valid here. 
        self.assertTrue(\
                segment.is_segmentv2("S\t3\t21\tTGCAACGTATAGACTTGTCAC\tRC:i:4"))

        
    def test_Fragment(self):
        with self.assertRaises(line.InvalidLineError):
            fragment.Fragment.from_string("    ")
        with self.assertRaises(line.InvalidLineError):
            fragment.Fragment.from_string("12\t2-\t0\t")
        with self.assertRaises(fv.InvalidFieldError):
            fragment.Fragment.from_string("2-\t0\t140$\t0\t140\t11M\tAA:Z:test")
                    
        frag = fragment.Fragment.from_string("F\t12\t2-\t0\t140$\t0\t140\t11M\tAA:Z:test")
        self.assertTrue(frag.type == "F")
        self.assertTrue(frag.fields['sid'].value == "12")
        self.assertTrue(frag.fields['external'].value == "2-")
        self.assertTrue(frag.fields['sbeg'].value == "0")
        self.assertTrue(frag.fields['send'].value == "140$")
        self.assertTrue(frag.fields['fbeg'].value == "0")
        self.assertTrue(frag.fields['fend'].value == "140")
        self.assertTrue(frag.fields['alignment'].value  == "11M")
        self.assertTrue(fragment.Fragment.is_valid(frag))


    def test_Edge(self):
        with self.assertRaises(line.InvalidLineError):
            edge.Edge.from_string("    ")
        with self.assertRaises(line.InvalidLineError):
            edge.Edge.from_string("*\t23-\t16+\t0\t11\t0\t11")

        with self.assertRaises(fv.InvalidFieldError):
            edge.Edge.from_string("23-\t16+\t0\t11\t0\t11\t11M\tAA:Z:test")
            
        edg = edge.Edge.from_string("E\t*\t23-\t16+\t0\t11\t0\t11\t11M\tAA:Z:test")
        self.assertTrue(edg.type == "E")
        self.assertTrue(edg.fields['eid'].value == "*")
        self.assertTrue(edg.fields['sid1'].value == "23-")
        self.assertTrue(edg.fields['sid2'].value == "16+")
        self.assertTrue(edg.fields['beg1'].value == "0")
        self.assertTrue(edg.fields['end2'].value == "11")
        self.assertTrue(edg.fields['beg1'].value == "0")
        self.assertTrue(edg.fields['end2'].value == "11")
        self.assertTrue(edg.fields['alignment'].value  == "11M")
        self.assertTrue(edge.Edge.is_valid(edg))

        
    def test_Link(self):
        with self.assertRaises(line.InvalidLineError):
            link.Link.from_string("    ")
        with self.assertRaises(line.InvalidLineError):
            link.Link.from_string("t3\t+\t65\t-")
        with self.assertRaises(fv.InvalidFieldError):
            link.Link.from_string("L\t+\t65\t-\t47M\tAA:Z:test")
        
        ln = link.Link.from_string("L\t3\t+\t65\t-\t47M\tAA:Z:test")
        self.assertTrue(ln.type == "L")
        self.assertTrue(ln.fields['from'].value == "3")
        self.assertTrue(ln.fields['from_orn'].value == "+")
        self.assertTrue(ln.fields['to'].value == "65")
        self.assertTrue(ln.fields['to_orn'].value == "-")
        self.assertTrue(ln.fields['overlap'].value == "47M")
        self.assertTrue(link.Link.is_valid(ln))

        
    def test_Containment(self):
        """
        Example taken from gfapy doc:  
            http://gfapy.readthedocs.io/en/latest/tutorial/gfa.html
        """
        # give a string with three fields instead of 4
        with self.assertRaises(line.InvalidLineError):
            containment.Containment.from_string("    ")
        with self.assertRaises(line.InvalidLineError):
            containment.Containment.from_string("a\t+\tb\t-\t10")

        with self.assertRaises(fv.InvalidFieldError):
            containment.Containment.from_string("+\tb\t-\t10\t*\tAA:Z:an optional field")
            
        cn = containment.Containment.from_string("C\ta\t+\tb\t-\t10\t*\tAA:Z:an optional field")
        self.assertTrue(cn.type == "C")
        self.assertTrue(cn.fields['from'].value == "a")
        self.assertTrue(cn.fields['from_orn'].value == "+")
        self.assertTrue(cn.fields['to'].value == "b")
        self.assertTrue(cn.fields['to_orn'].value == "-")
        self.assertTrue(cn.fields['pos'].value == 10)
        self.assertTrue(cn.fields['overlap'].value == "*")
        self.assertTrue(cn.fields['AA'].value == "an optional field")
        self.assertTrue(containment.Containment.is_valid(cn))


    def test_Gap(self):
        """
        Example taken from gfapy doc:
        http://gfapy.readthedocs.io/en/latest/tutorial/gfa.html_
        """
        with self.assertRaises(line.InvalidLineError):
            gap.Gap.from_string("    ")
        with self.assertRaises(line.InvalidLineError):
            gap.Gap.from_string("A+\tB-\t1000\t*")

        with self.assertRaises(fv.InvalidFieldError):
            gap.Gap.from_string("\G\tg\tA+\tB-\t*\tAA:Z:test")
        
        gp = gap.Gap.from_string("G\tg\tA+\tB-\t1000\t*\tAA:Z:test")
        self.assertTrue(gp.type == "G")
        self.assertTrue(gp.fields['gid'].value == "g")
        self.assertTrue(gp.fields['sid1'].value == "A+")
        self.assertTrue(gp.fields['sid2'].value == "B-")
        self.assertTrue(gp.fields['distance'].value == 1000)
        self.assertTrue(gp.fields['variance'].value  == "*")
        self.assertTrue(gap.Gap.is_valid(gp))


    def test_Path(self):
        with self.assertRaises(line.InvalidLineError):
            path.Path.from_string("    ")
        with self.assertRaises(line.InvalidLineError):
            path.Path.from_string("A+,X+,B+\t4M,4M")
        with self.assertRaises(fv.InvalidFieldError):
            path.Path.from_string("A+,X+,B+\t4M,4M\tAA:Z:test")
        
        pt = path.Path.from_string("P\tP1\tA+,X+,B+\t4M,4M\tAA:Z:test")
        self.assertTrue(pt.type == "P")
        self.assertTrue(pt.fields['path_name'].value == "P1")
        self.assertTrue(pt.fields['seqs_names'].value  == "A+,X+,B+".split(","))
        self.assertTrue(pt.fields['overlaps'].value  == "4M,4M".split(","))
        self.assertTrue(path.Path.is_valid(pt))
        
        
    def test_OGroup(self):
        with self.assertRaises(line.InvalidLineError):
            group.OGroup.from_string("    ")
        with self.assertRaises(line.InvalidLineError):
            group.OGroup.from_string("12- 11+ 32+ 28- 20- 16+")

        with self.assertRaises(fv.InvalidFieldError):
            group.OGroup.from_string("1p\tAA:Z:test")
        
        ogroup = group.OGroup.from_string("O\t1p\t12- 11+ 32+ 28- 20- 16+\tAA:Z:test")
        self.assertTrue(ogroup.type == "O")
        self.assertTrue(ogroup.fields['oid'].value == "1p")
        self.assertTrue(ogroup.fields['references'].value  == "12- 11+ 32+ 28- 20- 16+".split())
        self.assertTrue(group.OGroup.is_valid(ogroup))
        
    def test_UGroup(self):
        with self.assertRaises(line.InvalidLineError):
            group.UGroup.from_string("    ")
        with self.assertRaises(line.InvalidLineError):
            group.UGroup.from_string("A b_c g")

        with self.assertRaises(fv.InvalidFieldError):
            group.UGroup.from_string("s1\t\tAA:Z:test")

        ugroup = group.UGroup.from_string("U\ts1\tA b_c g\tAA:Z:test")
        self.assertTrue(ugroup.type == "U")
        self.assertTrue(ugroup.fields['uid'].value == "s1")
        self.assertTrue(ugroup.fields['ids'].value  == "A b_c g".split())
        self.assertTrue(group.UGroup.is_valid(ugroup))



if  __name__ == '__main__':
    unittest.main()
