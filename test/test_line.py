import sys
sys.path.insert(0, '../')

from pygfa.graph_element.parser import header, segment, link, path, containment, fragment, edge, gap, group
from pygfa.graph_element.parser import line, field_validator as fv
import re
import unittest

"""
Tips: How to TDD with regex
https://stackoverflow.com/questions/488601/how-do-you-unit-test-regular-expressions
"""

class TestField():
    """!
    A test class that similar to optfield, but without name and allows to
    have any type of field listed in field_validator dictionary of types.
    It's just a custom class to easily check the different types of fields.
    If a TestField object can be initialized, the value respects its field type.
    """
    def __init__ (self, value, field_type):
        self.type = field_type
        self.value = fv.validate (value, field_type)


        

class TestLine (unittest.TestCase):

    def test_Field (self):
        """Use TestField to check how the different field data types
        are managed."""

        with self.assertRaises (fv.UnknownDataTypeError):
            optf = TestField ('bb', 'c') # c is an invalid type of field

        optf = TestField ('A', 'A')
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('aa', 'A')
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('', 'A')
        
        optf = TestField ('-42', 'i')
        self.assertTrue (optf.value == -42)
        optf = TestField ('+42', 'i')
        optf = TestField ('42', 'i')
        self.assertTrue (optf.value == +42)
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('aa', 'i')
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('', 'i')

        optf = TestField ('-1.4241e-11', 'f')
        optf = TestField ('+1.4241E+11', 'f')
        optf = TestField ('42', 'f')
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('A', 'f')
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('042e0.5', 'f')
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('', 'f')

        optf = TestField ('The gray fox jumped from somewhere...', 'Z')
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('力 - is the force', 'Z')
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('\n - is the force', 'Z')
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('', 'Z')

        # TODO: check for json parser/verifier existence within python (should exists)
        # this test should fail
        optf = TestField ('The gray fox jumped from somewhere...', 'J')
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('力 - is the force', 'J')
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('\n - is the force', 'J')
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('', 'J')

        ##################################################################

        optf = TestField ('A5F', 'H')
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('a5f', 'H')
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('g', 'H')
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('', 'H')


        optf = TestField ('c,15,17,21,-32', 'B')
        optf = TestField ('f,15,.05e4', 'B')
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('f15,i.05e4', 'B')
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('', 'B')


        optf = TestField ('(12', fv.GFA1_NAME)
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('', fv.GFA1_NAME)

        optf = TestField ('+', fv.GFA1_ORIENTATION)
        optf = TestField ('-', fv.GFA1_ORIENTATION)
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('', fv.GFA1_ORIENTATION)
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('++', fv.GFA1_ORIENTATION)
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('a', fv.GFA1_ORIENTATION)
        
        optf = TestField ('(12-,14+,17-', fv.GFA1_NAMES)
        optf = TestField ('(12-,14,17-', fv.GFA1_NAMES) # no sign orientation near 14
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('(12-, 14+,17-', fv.GFA1_NAMES) # space is not allowed
                # even for separating elements in the array
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('', fv.GFA1_NAMES)

        optf = TestField ('acgt', fv.GFA1_SEQUENCE)
        optf = TestField ('*', fv.GFA1_SEQUENCE)
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('*acgt', fv.GFA1_SEQUENCE)
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('', fv.GFA1_SEQUENCE)

        optf = TestField ('0', fv.GFA1_INT)
        optf = TestField ('100', fv.GFA1_INT)
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('-1', fv.GFA1_INT)
        # TODO: Solve asking for clearance
        # with self.assertRaises (fv.InvalidFieldError):
        #    optf = TestField ('', 'pos')

        optf = TestField ('*', fv.GFA1_CIGAR)
        optf = TestField ('5I2M', fv.GFA1_CIGAR)
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('', fv.GFA1_CIGAR)

        optf = TestField ('*,*,*', fv.GFA1_CIGARS)
        optf = TestField ('*', fv.GFA1_CIGARS)
        optf = TestField ('5I2M,*,3X,22M', fv.GFA1_CIGARS)
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('', fv.GFA1_CIGARS)
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('5I2M,*,3,22M', fv.GFA1_CIGARS) # operation not specified (M, I, D...)

        optf = TestField ('5I2M', fv.GFA2_CIGAR)
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('', fv.GFA2_CIGAR)
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('*', fv.GFA2_CIGAR)
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('5I3X', fv.GFA2_CIGAR)

        optf = TestField ('aa', fv.GFA2_ID)
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('', fv.GFA2_ID)
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('a a', fv.GFA2_ID)

        optf = TestField ('aa', fv.GFA2_IDS)
        self.assertTrue (optf.value == ['aa'])
        optf = TestField ('aa bb cc dd', fv.GFA2_IDS)
        self.assertTrue (optf.value == ['aa', 'bb', 'cc', 'dd'])
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('', fv.GFA2_IDS)
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('a  b', fv.GFA2_IDS) # there are 2 spaces between the a and the b

        optf = TestField ('aa+', fv.GFA2_REFERENCE)
        optf = TestField ('aa-', fv.GFA2_REFERENCE)
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('', fv.GFA2_REFERENCE)
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('aa', fv.GFA2_REFERENCE)

        optf = TestField ('aa+', fv.GFA2_REFERENCES)
        self.assertTrue (optf.value == ['aa+'])
        optf = TestField ('aa+ bb- cc+ dd-', fv.GFA2_REFERENCES)
        self.assertTrue (optf.value == ['aa+', 'bb-', 'cc+', 'dd-'])
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('', fv.GFA2_REFERENCES)
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('aa bb+', fv.GFA2_REFERENCES)

        optf = TestField ('42', fv.GFA2_INT)
        self.assertTrue (optf.value == 42)
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('', fv.GFA2_INT)
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('-42', fv.GFA2_INT)

        optf = TestField ('42', fv.GFA2_TRACE)
        optf = TestField ('42,42', fv.GFA2_TRACE)
        optf = TestField ('42,42,42', fv.GFA2_TRACE)
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('', fv.GFA2_TRACE)
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('-42', fv.GFA2_TRACE)

        optf = TestField ('42', fv.GFA2_POSITION)
        self.assertTrue (optf.value == "42") # pos2 will be a string
        optf = TestField ('42$', fv.GFA2_POSITION)
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('', fv.GFA2_POSITION)
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('$', fv.GFA2_POSITION)
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('1$$', fv.GFA2_POSITION)

        optf = TestField ('*', fv.GFA2_SEQUENCE)
        optf = TestField ('acgtACGTXYZ', fv.GFA2_SEQUENCE)
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('', fv.GFA2_SEQUENCE)

        optf = TestField ('aa', fv.GFA2_OPTIONAL_ID)
        optf = TestField ('*', fv.GFA2_OPTIONAL_ID)
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('', fv.GFA2_OPTIONAL_ID)
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('* ', fv.GFA2_OPTIONAL_ID)

        optf = TestField ('42,42,42', fv.GFA2_ALIGNMENT)
        optf = TestField ('*', fv.GFA2_ALIGNMENT)
        optf = TestField ('2I3M', fv.GFA2_ALIGNMENT)
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('', fv.GFA2_ALIGNMENT)
        with self.assertRaises (fv.InvalidFieldError):
            optf = TestField ('42,13M', fv.GFA2_ALIGNMENT)

        # Missing field type tests
        # 'pos' : "^[0-9]*$", # positive integer \ TODO: this way the empty string is allowed... could it be possibly a
        # mistake in the specification of GFA1? Ask for it.
        #
        # 'cmt' : ".*"


    def test_Fields (self):
        field = line.OptField ("na", "test", "Z")
        with self.assertRaises (ValueError):
            field = line.OptField ("aa", "test", "lbl")


    def test_Segment (self):
        """Test the parsing of a S line either following the GFA1 and the GFA2 specifications."""
        seg = segment.SegmentV1.from_string ("S\t3\tTGCAACGTATAGACTTGTCAC\tRC:i:4")
        self.assertTrue (seg.type == "S")
        self.assertTrue (seg.fields['name'].value == "3")
        self.assertTrue (seg.fields['sequence'].value  == "TGCAACGTATAGACTTGTCAC")
        self.assertTrue (seg.fields['RC'].value == 4)

        seg = segment.SegmentV2.from_string ("S\t3\t21\tTGCAACGTATAGACTTGTCAC\tRC:i:4")
        self.assertTrue (seg.type == "S")
        self.assertTrue (seg.fields['sid'].value == "3")
        self.assertTrue (seg.fields['slen'].value == 21)
        self.assertTrue (seg.fields['sequence'].value  == "TGCAACGTATAGACTTGTCAC")
        self.assertTrue (seg.fields['RC'].value == 4)

        
    def test_Fragment (self):
        frag = fragment.Fragment.from_string ("F\t12\t2-\t0\t140$\t0\t140\t11M")
        self.assertTrue (frag.type == "F")
        self.assertTrue (frag.fields['sid'].value == "12")
        self.assertTrue (frag.fields['external'].value == "2-")
        self.assertTrue (frag.fields['sbeg'].value == "0")
        self.assertTrue (frag.fields['send'].value == "140$")
        self.assertTrue (frag.fields['fbeg'].value == "0")
        self.assertTrue (frag.fields['fend'].value == "140")
        self.assertTrue (frag.fields['alignment'].value  == "11M")


    def test_Edge (self):
        edg = edge.Edge.from_string ("E\t*\t23-\t16+\t0\t11\t0\t11\t11M")
        self.assertTrue (edg.type == "E")
        self.assertTrue (edg.fields['eid'].value == "*")
        self.assertTrue (edg.fields['sid1'].value == "23-")
        self.assertTrue (edg.fields['sid2'].value == "16+")
        self.assertTrue (edg.fields['beg1'].value == "0")
        self.assertTrue (edg.fields['end2'].value == "11")
        self.assertTrue (edg.fields['beg1'].value == "0")
        self.assertTrue (edg.fields['end2'].value == "11")
        self.assertTrue (edg.fields['alignment'].value  == "11M")

        
    def test_Link (self):
        ln = link.Link.from_string ("L\t3\t+\t65\t-\t47M")
        self.assertTrue (ln.type == "L")
        self.assertTrue (ln.fields['from'].value == "3")
        self.assertTrue (ln.fields['from_orn'].value == "+")
        self.assertTrue (ln.fields['to'].value == "65")
        self.assertTrue (ln.fields['to_orn'].value == "-")
        self.assertTrue (ln.fields['overlap'].value == "47M")

        
    def test_Containment (self):
        cn = containment.Containment.from_string ("C\ta\t+\tb\t-\t10\t*") # example taken from gfapy doc: http://gfapy.readthedocs.io/en/latest/tutorial/gfa.html
        self.assertTrue (cn.type == "C")
        self.assertTrue (cn.fields['from'].value == "a")
        self.assertTrue (cn.fields['from_orn'].value == "+")
        self.assertTrue (cn.fields['to'].value == "b")
        self.assertTrue (cn.fields['to_orn'].value == "-")
        self.assertTrue (cn.fields['pos'].value == 10)
        self.assertTrue (cn.fields['overlap'].value == "*")


    def test_Gap (self):
        gp = gap.Gap.from_string ("G\tg\tA+\tB-\t1000\t*") # example taken from gfapy doc: http://gfapy.readthedocs.io/en/latest/tutorial/gfa.html
        self.assertTrue (gp.type == "G")
        self.assertTrue (gp.fields['gid'].value == "g")
        self.assertTrue (gp.fields['sid1'].value == "A+")
        self.assertTrue (gp.fields['sid2'].value == "B-")
        self.assertTrue (gp.fields['distance'].value == 1000)
        self.assertTrue (gp.fields['variance'].value  == "*")


    def test_Path (self):
        pt = path.Path.from_string ("P\tP1\tA+,X+,B+\t4M,4M")
        self.assertTrue (pt.type == "P")
        self.assertTrue (pt.fields['path_name'].value == "P1")
        self.assertTrue (pt.fields['seqs_names'].value  == "A+,X+,B+".split (","))
        self.assertTrue (pt.fields['overlaps'].value  == "4M,4M".split (","))
        
        
    def test_OGroup (self):
        ogroup = group.OGroup.from_string ("O\t1p\t12- 11+ 32+ 28- 20- 16+")
        self.assertTrue (ogroup.type == "O")
        self.assertTrue (ogroup.fields['oid'].value == "1p")
        self.assertTrue (ogroup.fields['references'].value  == "12- 11+ 32+ 28- 20- 16+".split ())

        
    def test_UGroup (self):
        ugroup = group.UGroup.from_string ("U\ts1\tA b_c g")
        self.assertTrue (ugroup.type == "U")
        self.assertTrue (ugroup.fields['uid'].value == "s1")
        self.assertTrue (ugroup.fields['ids'].value  == "A b_c g".split ())



if  __name__ == '__main__':
    unittest.main()
