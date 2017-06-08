import sys
sys.path.insert(0, '../pygfa')

from parser.lines import header, segment, link, path, containment, fragment, edge, gap
from parser import error, line, field_validator as fv
import re
import unittest

"""
Tips: How to TDD with regex
https://stackoverflow.com/questions/488601/how-do-you-unit-test-regular-expressions
"""

class TestField():
    """A test class that similar to optfield, but without name and allows to
    have any type of field listed in field_validator dictionary of types.
    It's just a custom class to easily check the different types of fields.
    If a TestField object can be initialized, the value respects its field type."""
    def __init__ (self, value, field_type):
        self.type = field_type
        self.value = fv.validate (value, field_type)


        

class TestLine (unittest.TestCase):

    def test_Field (self):
        """Use TestField to check how the different field data types
        are managed."""

        with self.assertRaises (error.UnknownDataTypeError):
            optf = TestField ('bb', 'c') # c is an invalid type of field

        optf = TestField ('A', 'A')
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('aa', 'A')
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('', 'A')
        
        optf = TestField ('-42', 'i')
        self.assertTrue (optf.value == -42)
        optf = TestField ('+42', 'i')
        optf = TestField ('42', 'i')
        self.assertTrue (optf.value == +42)
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('aa', 'i')
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('', 'i')

        optf = TestField ('-1.4241e-11', 'f')
        optf = TestField ('+1.4241E+11', 'f')
        optf = TestField ('42', 'f')
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('A', 'f')
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('042e0.5', 'f')
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('', 'f')

        optf = TestField ('The gray fox jumped from somewhere...', 'Z')
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('力 - is the force', 'Z')
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('\n - is the force', 'Z')
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('', 'Z')

        # TODO: check for json parser/verifier existence within python (should exists)
        # this test should fail
        optf = TestField ('The gray fox jumped from somewhere...', 'J')
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('力 - is the force', 'J')
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('\n - is the force', 'J')
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('', 'J')

        ##################################################################

        optf = TestField ('A5F', 'H')
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('a5f', 'H')
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('g', 'H')
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('', 'H')


        optf = TestField ('c,15,17,21,-32', 'B')
        optf = TestField ('f,15,.05e4', 'B')
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('f15,i.05e4', 'B')
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('', 'B')


        optf = TestField ('(12', 'lbl')
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('', 'lbl')

        optf = TestField ('+', 'orn')
        optf = TestField ('-', 'orn')
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('', 'orn')
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('++', 'orn')
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('a', 'orn')
        
        optf = TestField ('(12-,14+,17-', 'lbs')
        optf = TestField ('(12-,14,17-', 'lbs') # no sign orientation near 14
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('(12-, 14+,17-', 'lbs') # space is not allowed
                # even for separating elements in the array
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('', 'lbs')

        optf = TestField ('acgt', 'seq')
        optf = TestField ('*', 'seq')
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('*acgt', 'seq')
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('', 'seq')

        optf = TestField ('0', 'pos')
        optf = TestField ('100', 'pos')
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('-1', 'pos')
        # TODO: Solve asking for clearance
        # with self.assertRaises (error.InvalidFieldError):
        #    optf = TestField ('', 'pos')

        optf = TestField ('*', 'cig')
        optf = TestField ('5I2M', 'cig')
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('', 'cig')

        optf = TestField ('*,*,*', 'cgs')
        optf = TestField ('*', 'cgs')
        optf = TestField ('5I2M,*,3X,22M', 'cgs')
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('', 'cgs')
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('5I2M,*,3,22M', 'cgs') # operation not specified (M, I, D...)

        optf = TestField ('5I2M', 'cig2')
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('', 'cig2')
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('*', 'cig2')
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('5I3X', 'cig2')

        optf = TestField ('aa', 'id')
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('', 'id')
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('a a', 'id')

        optf = TestField ('aa', 'ids')
        self.assertTrue (optf.value == ['aa'])
        optf = TestField ('aa bb cc dd', 'ids')
        self.assertTrue (optf.value == ['aa', 'bb', 'cc', 'dd'])
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('', 'ids')
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('a  b', 'ids') # there are 2 spaces between the a and the b

        optf = TestField ('aa+', 'ref')
        optf = TestField ('aa-', 'ref')
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('', 'ref')
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('aa', 'ref')

        optf = TestField ('aa+', 'rfs')
        self.assertTrue (optf.value == ['aa+'])
        optf = TestField ('aa+ bb- cc+ dd-', 'rfs')
        self.assertTrue (optf.value == ['aa+', 'bb-', 'cc+', 'dd-'])
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('', 'rfs')
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('aa bb+', 'rfs')

        optf = TestField ('42', 'int')
        self.assertTrue (optf.value == 42)
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('', 'int')
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('-42', 'int')

        optf = TestField ('42', 'trc')
        optf = TestField ('42,42', 'trc')
        optf = TestField ('42,42,42', 'trc')
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('', 'trc')
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('-42', 'trc')

        optf = TestField ('42', 'pos2')
        self.assertTrue (optf.value == "42") # pos will be a string
        optf = TestField ('42$', 'pos2')
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('', 'pos2')
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('$', 'pos2')
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('1$$', 'pos2')

        optf = TestField ('*', 'seq2')
        optf = TestField ('acgtACGTXYZ', 'seq2')
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('', 'seq2')

        optf = TestField ('aa', 'oid')
        optf = TestField ('*', 'oid')
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('', 'oid')
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('* ', 'oid')

        optf = TestField ('42,42,42', 'aln')
        optf = TestField ('*', 'aln')
        optf = TestField ('2I3M', 'aln')
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('', 'aln')
        with self.assertRaises (error.InvalidFieldError):
            optf = TestField ('42,13M', 'aln')

        # Missing field type tests
        # 'pos' : "^[0-9]*$", # positive integer \ TODO: this way the empty string is allowed... could it be possibly a
        # mistake in the specification of GFA1? Ask for it.
        #
        # 'cmt' : ".*", # conten
        # t of comment line, everything is allowed \
                                        

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


    def test_Gap (self):
        gp = gap.Gap.from_string ("G\tg\tA+\tB-\t1000\t*") # example taken from gfapy doc: http://gfapy.readthedocs.io/en/latest/tutorial/gfa.html
        self.assertTrue (gp.type == "E")
        self.assertTrue (gp.fields['gid'].value == "g")
        self.assertTrue (gp.fields['sid1'].value == "A+")
        self.assertTrue (gp.fields['sid2'].value == "B-")
        self.assertTrue (gp.fields['displacement'].value == "1000")
        self.assertTrue (gp.fields['variance'].value  == "*")



if  __name__ == '__main__':
    unittest.main()
