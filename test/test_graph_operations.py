import unittest
import sys
import tempfile
import os
from pathlib import Path

sys.path.insert(0, "../")

from pygfa.graph_operations.compression import (
    tuple_to_string,
    reverse_and_complement,
    reverse_strand,
)
from pygfa.graph_operations.overlap_consistency import (
    reverse_and_complement as overlap_reverse_complement,
    fasta_reader,
    real_overlap,
)


class TestGraphOperationsBase(unittest.TestCase):
    """Base class for graph operation tests with proper temp file handling."""

    def setUp(self):
        """Set up test output directory."""
        # Create output directory for this test class
        self.test_output_dir = Path("results/test/graph_operations")
        self.test_output_dir.mkdir(parents=True, exist_ok=True)

    def get_temp_file(self, suffix=".tmp"):
        """Create a temporary file in the test output directory."""
        fd, path = tempfile.mkstemp(suffix=suffix, dir=str(self.test_output_dir))
        os.close(fd)
        return path


class TestCompressionOperations(TestGraphOperationsBase):
    """Test graph compression operations."""

    def test_tuple_to_string(self):
        """Test tuple to string conversion."""
        result = tuple_to_string(("node1", "+"))
        self.assertEqual(result, "node1|+")

        result = tuple_to_string(("node2", "-"))
        self.assertEqual(result, "node2|-")

    def test_reverse_and_complement(self):
        """Test reverse complement of DNA sequences."""
        # Test standard bases
        result = reverse_and_complement("ATCG")
        self.assertEqual(result, "CGAT")

        # Test with wildcard
        result = reverse_and_complement("*")
        self.assertEqual(result, "*")

        # Test mixed case
        result = reverse_and_complement("aTcG")
        self.assertEqual(result, "CGAT")

    def test_reverse_strand(self):
        """Test strand reversal."""
        self.assertEqual(reverse_strand("+"), "-")
        self.assertEqual(reverse_strand("-"), "+")
        self.assertIsNone(reverse_strand(None))
        self.assertIsNone(reverse_strand(""))

    def test_update_graph_basic(self):
        """Test basic graph update operations."""
        # This would require a mock GFA graph for testing
        # For now, just test the helper functions work
        self.assertEqual(tuple_to_string(("node1", "+")), "node1|+")


class TestOverlapConsistency(TestGraphOperationsBase):
    """Test overlap consistency operations."""

    def test_reverse_and_complement_overlap(self):
        """Test reverse complement for overlap consistency."""
        result = overlap_reverse_complement("ATCG")
        self.assertEqual(result, "CGAT")

        result = overlap_reverse_complement("*")
        self.assertEqual(result, "*")

    def test_real_overlap(self):
        """Test real overlap calculation."""
        # Test perfect match
        result = real_overlap("ATCGG", "GCGAA")
        self.assertEqual(result, 2)  # "GC" matches

        # Test no overlap
        result = real_overlap("ATCG", "GCTA")
        self.assertEqual(result, 0)

        # Test partial overlap
        result = real_overlap("ATCGAAA", "AAAGCCC")
        self.assertEqual(result, 3)  # "AAA" matches

        # Test empty strings
        result = real_overlap("", "ATCG")
        self.assertEqual(result, 0)
        result = real_overlap("ATCG", "")
        self.assertEqual(result, 0)

    def test_fasta_reader(self):
        """Test FASTA file reading."""
        # Create a temporary FASTA file
        fasta_content = ">seq1\nATCG\n>seq2\nGCTA\n"

        temp_file = self.get_temp_file(suffix=".fasta")
        with open(temp_file, "w") as f:
            f.write(fasta_content)

        try:
            # Test reading valid FASTA
            result = fasta_reader("", os.path.basename(temp_file))
            self.assertIsNotNone(result)
            if result:  # Check result is not None
                self.assertEqual(result["seq1"], "ATCG")
                self.assertEqual(result["seq2"], "GCTA")

            # Test reading non-existent file
            result = fasta_reader("", "non_existent.fasta")
            self.assertIsNone(result)

        finally:
            # Clean up
            if os.path.exists(temp_file):
                os.unlink(temp_file)


class TestGraphOperationsIntegration(TestGraphOperationsBase):
    """Integration tests for graph operations."""

    def test_compression_workflow(self):
        """Test a typical compression workflow."""
        # Test that sequence operations work together
        sequence = "ATCGATCG"

        # Reverse complement
        rc_seq = reverse_and_complement(sequence)
        self.assertEqual(rc_seq, "CGATCGAT")

        # Convert to tuple string format
        tuple_str = tuple_to_string(("node1", "+"))
        self.assertEqual(tuple_str, "node1|+")

        # Verify strand reversal
        self.assertEqual(reverse_strand("+"), "-")
        self.assertEqual(reverse_strand("-"), "+")

    def test_overlap_analysis_workflow(self):
        """Test overlap analysis workflow."""
        seq1 = "ATCGGGG"
        seq2 = "GGGCTA"

        # Calculate real overlap
        overlap = real_overlap(seq1, seq2)
        self.assertEqual(overlap, 4)  # "GGGG" overlaps

        # Get reverse complement for further analysis
        rc_seq2 = overlap_reverse_complement(seq2)
        self.assertEqual(rc_seq2, "TAGCCC")


if __name__ == "__main__":
    unittest.main()
