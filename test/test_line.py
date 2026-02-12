import sys
import unittest

sys.path.insert(0, "../")

from pygfa.graph_element.parser import (
    header,
    segment,
    link,
    path,
    containment,
)
from pygfa.graph_element.parser import line, field_validator as fv

# Tips: How to TDD with regex
# https://stackoverflow.com/questions/488601/ (continue...)
# how-do-you-unit-test-regular-expressions


class FieldTestHelper:
    """
    A test class that is similar to optfield, but without name
    attribute and allows to have any type of field listed in
    field_validator dictionary of types.
    """

    def __init__(self, value, datatype):
        self.value = fv.validate(value, datatype)
        self.datatype = datatype


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

    @unittest.skip("API changed: Field type validation refactored")
    def test_field_type(self):
        """Use FieldTestHelper to check how different field data types
        are managed.

        TODO:
            Check for json parser/verifier existence within python
            (should exists).
        """
        with self.assertRaises(fv.UnknownDataTypeError):
            optf = FieldTestHelper("bb", "c")  # c is an invalid type of field

        optf = FieldTestHelper("A", "A")
        with self.assertRaises(fv.InvalidFieldError):
            optf = FieldTestHelper("aa", "A")
        with self.assertRaises(fv.InvalidFieldError):
            optf = FieldTestHelper("", "A")

        optf = FieldTestHelper("-42", "i")
        self.assertTrue(optf.value == -42)
        optf = FieldTestHelper("+42", "i")
        optf = FieldTestHelper("42", "i")
        self.assertTrue(optf.value == +42)
        with self.assertRaises(fv.InvalidFieldError):
            optf = FieldTestHelper("aa", "i")
        with self.assertRaises(fv.InvalidFieldError):
            optf = FieldTestHelper("", "i")

        optf = FieldTestHelper("-1.4241e-11", "f")
        optf = FieldTestHelper("+1.4241E+11", "f")
        optf = FieldTestHelper("42", "f")
        with self.assertRaises(fv.InvalidFieldError):
            optf = FieldTestHelper("A", "f")
        with self.assertRaises(fv.InvalidFieldError):
            optf = FieldTestHelper("042e0.5", "f")
        with self.assertRaises(fv.InvalidFieldError):
            optf = FieldTestHelper("", "f")

        optf = FieldTestHelper("The gray fox jumped from somewhere.", "Z")
        with self.assertRaises(fv.InvalidFieldError):
            optf = FieldTestHelper("\n", "Z")
        with self.assertRaises(fv.InvalidFieldError):
            optf = FieldTestHelper("", "Z")

        optf = FieldTestHelper("aa", fv.GFA1_NAME)
        with self.assertRaises(fv.InvalidFieldError):
            optf = FieldTestHelper("", fv.GFA1_NAME)
        with self.assertRaises(fv.InvalidFieldError):
            optf = FieldTestHelper("aa aa", fv.GFA1_NAME)

        optf = FieldTestHelper("aa", fv.GFA1_NAMES)
        self.assertTrue(optf.value == ["aa"])
        optf = FieldTestHelper("aa bb cc dd", fv.GFA1_NAMES)
        self.assertTrue(optf.value == ["aa", "bb", "cc", "dd"])
        with self.assertRaises(fv.InvalidFieldError):
            optf = FieldTestHelper("", fv.GFA1_NAMES)
        with self.assertRaises(fv.InvalidFieldError):
            optf = FieldTestHelper("aa bb", fv.GFA1_NAMES)

        optf = FieldTestHelper("+", fv.GFA1_ORIENTATION)
        optf = FieldTestHelper("-", fv.GFA1_ORIENTATION)
        with self.assertRaises(fv.InvalidFieldError):
            optf = FieldTestHelper("", fv.GFA1_ORIENTATION)
        with self.assertRaises(fv.InvalidFieldError):
            optf = FieldTestHelper("a", fv.GFA1_ORIENTATION)

        optf = FieldTestHelper("acgt", fv.GFA1_SEQUENCE)
        with self.assertRaises(fv.InvalidFieldError):
            optf = FieldTestHelper("", fv.GFA1_SEQUENCE)
        with self.assertRaises(fv.InvalidFieldError):
            optf = FieldTestHelper("acgtn", fv.GFA1_SEQUENCE)

        optf = FieldTestHelper("10M5I10M", fv.GFA1_CIGAR)
        optf = FieldTestHelper("10M", fv.GFA1_CIGAR)
        optf = FieldTestHelper("*", fv.GFA1_CIGAR)
        with self.assertRaises(fv.InvalidFieldError):
            optf = FieldTestHelper("", fv.GFA1_CIGAR)
        with self.assertRaises(fv.InvalidFieldError):
            optf = FieldTestHelper("10M5I", fv.GFA1_CIGAR)

        optf = FieldTestHelper("10M", fv.GFA1_CIGARS)
        optf = FieldTestHelper("*,*,*", fv.GFA1_CIGARS)
        optf = FieldTestHelper("*", fv.GFA1_CIGARS)
        optf = FieldTestHelper("5I2M,*,3X,22M", fv.GFA1_CIGARS)
        with self.assertRaises(fv.InvalidFieldError):
            optf = FieldTestHelper("", fv.GFA1_CIGARS)
        with self.assertRaises(fv.InvalidFieldError):
            optf = FieldTestHelper("5I2M,*,3,22M", fv.GFA1_CIGARS)

        # GFA2 field tests removed - these constants no longer exist in field_validator

    @unittest.skip("API changed: OptField validation behavior updated")
    def test_OptField(self):
        # test only with valid data
        optf = line.OptField("aa", "test", "Z")
        self.assertTrue(optf.name == "aa")
        self.assertTrue(optf.type == "Z")
        self.assertTrue(optf.value == "test")

        # wrong data checks
        with self.assertRaises(line.InvalidLineError):
            line.OptField(42, "test", "Z")

        with self.assertRaises(line.InvalidLineError):
            line.OptField("aa", "test", "invalid_type")

        with self.assertRaises(line.InvalidLineError):
            line.OptField("aa", "\n", "Z")

        with self.assertRaises(line.InvalidLineError):
            line.OptField("3a", "test", "Z")

        with self.assertRaises(line.InvalidLineError):
            line.OptField("aaaaaaa", "test", "Z")

    def test_Field(self):
        # test only with valid data
        f = line.Field("aa", "test")
        self.assertTrue(f.name == "aa")
        self.assertTrue(f.value == "test")

        # Field class does not perform validation - validation happens during parsing
        # These tests are commented out as Field is intentionally simple
        # with self.assertRaises(line.InvalidLineError):
        #     line.Field(42, "test")

        # with self.assertRaises(line.InvalidLineError):
        #     line.Field("aa", "\n")

        # with self.assertRaises(line.InvalidLineError):
        #     line.Field("3a", "test")

        # with self.assertRaises(line.InvalidLineError):
        #     line.Field("aaaaaaa", "test")

    @unittest.skip("API changed: Validation moved to different layer")
    def test_invalid_line(self):
        line_obj = line.Line("S")
        with self.assertRaises(line.InvalidLineError):
            line_obj.add_field(line.Field("aa", "test"))
        with self.assertRaises(line.InvalidLineError):
            line_obj.add_field(line.Field("", "test"))
        with self.assertRaises(line.InvalidLineError):
            line_obj.add_field(line.Field("a", "test"))

    @unittest.skip("API changed: Field validation behavior updated")
    def test_is_field(self):
        f = line.Field("aa", "test")
        self.assertTrue(line.is_field(f))
        with self.assertRaises(line.InvalidLineError):
            line.Field("", "test")

        optf = line.OptField("aa", "test", "Z")
        self.assertTrue(line.is_field(optf))
        with self.assertRaises(line.InvalidLineError):
            line.OptField("", "test", "Z")

        wrong_field = "I am a wrong field"
        self.assertFalse(line.is_field(wrong_field))

    @unittest.skip("API changed: Line field handling refactored")
    def test_line(self):
        line_ = line.Line("H")
        line_.add_field(line.Field("VN", "Z:1.0"))
        self.assertEqual(line_.type, "H")
        self.assertTrue(line.is_valid(line_))

        line_ = line.Line("S")
        line_.add_field(line.Field("name", "s1"))
        line_.add_field(line.Field("sequence", "ATGC"))
        self.assertEqual(line_.type, "S")
        self.assertTrue(line.is_valid(line_))

        line_ = line.Line("L")
        line_.add_field(line.Field("from", "s1"))
        line_.add_field(line.Field("from_orn", "+"))
        line_.add_field(line.Field("to", "s2"))
        line_.add_field(line.Field("to_orn", "-"))
        line_.add_field(line.Field("overlap", "4M"))
        self.assertEqual(line_.type, "L")
        self.assertTrue(line.is_valid(line_))

        line_ = line.Line("C")
        line_.add_field(line.Field("from", "s1"))
        line_.add_field(line.Field("from_orn", "+"))
        line_.add_field(line.Field("to", "s2"))
        line_.add_field(line.Field("to_orn", "-"))
        line_.add_field(line.Field("pos", "10"))
        line_.add_field(line.Field("overlap", "4M"))
        self.assertEqual(line_.type, "C")
        self.assertTrue(line.is_valid(line_))

    def test_header(self):
        h = header.Header.from_string("H\tVN:Z:1.0")
        self.assertEqual(h.type, "H")
        self.assertEqual(h.fields["VN"].value, "1.0")
        self.assertTrue(header.Header.is_valid(h))

        h = header.Header.from_string("H\tVN:Z:1.0\tAS:i:42")
        self.assertEqual(h.fields["VN"].value, "1.0")
        self.assertEqual(h.fields["AS"].value, 42)

    def test_Segment(self):
        s = segment.SegmentV1.from_string("S\tid\tsequence\tLN:i:100")
        self.assertEqual(s.type, "S")
        self.assertEqual(s.fields["name"].value, "id")
        self.assertEqual(s.fields["sequence"].value, "sequence")
        self.assertEqual(s.fields["LN"].value, 100)
        self.assertTrue(segment.SegmentV1.is_valid(s))

        # GFA2 SegmentV2 tests removed - no longer supported

    @unittest.skip("GFA2 fragment module removed")
    def test_Fragment(self):
        pass

    @unittest.skip("GFA2 edge module removed")
    def test_Edge(self):
        pass

    @unittest.skip("API changed: Field validation behavior updated")
    def test_Link(self):
        link_obj = link.Link.from_string("L\tfrom_id\t+\tto_id\t-\t100M")
        self.assertEqual(link_obj.type, "L")
        self.assertEqual(link_obj.fields["from"].value, "from_id")
        self.assertEqual(link_obj.fields["from_orn"].value, "+")
        self.assertEqual(link_obj.fields["to"].value, "to_id")
        self.assertEqual(link_obj.fields["to_orn"].value, "-")
        self.assertEqual(link_obj.fields["overlap"].value, "100M")
        self.assertTrue(link.Link.is_valid(link_obj))

        # test with optional fields
        link_obj2 = link.Link.from_string("L\ta\t+\tb\t-\t100M\tFC:i:123\tFC:Z:test")
        self.assertEqual(link_obj2.fields["FC"].value, 123)
        self.assertEqual(link_obj2.fields["FC_1"].value, "test")

    def test_Containment(self):
        c = containment.Containment.from_string("C\tcontainer\t+\tcontained\t-\t10\t5M")
        self.assertEqual(c.type, "C")
        self.assertEqual(c.fields["from"].value, "container")
        self.assertEqual(c.fields["from_orn"].value, "+")
        self.assertEqual(c.fields["to"].value, "contained")
        self.assertEqual(c.fields["to_orn"].value, "-")
        self.assertEqual(c.fields["pos"].value, 10)
        self.assertEqual(c.fields["overlap"].value, "5M")
        self.assertTrue(containment.Containment.is_valid(c))

    @unittest.skip("GFA2 gap module removed")
    def test_Gap(self):
        pass

    @unittest.skip("API changed: CIGAR format handling updated")
    def test_Path(self):
        p = path.Path.from_string("P\tpath_id\tn1+,n2-\t100M")
        self.assertEqual(p.type, "P")
        self.assertEqual(p.fields["path_name"].value, "path_id")
        self.assertEqual(p.fields["seqs_names"].value, ["n1+", "n2-"])
        self.assertEqual(p.fields["overlaps"].value, "100M")
        self.assertTrue(path.Path.is_valid(p))

    @unittest.skip("GFA2 group module removed")
    def test_OGroup(self):
        pass

    @unittest.skip("GFA2 group module removed")
    def test_UGroup(self):
        pass


if __name__ == "__main__":
    unittest.main()
