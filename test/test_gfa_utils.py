#!/usr/bin/env python3
"""Tests for GFA utility functions."""

from pygfa.gfa_utils import strip_gfa_comments


class TestStripGfaComments:
    """Test the strip_gfa_comments utility function."""

    def test_removes_comment_lines(self) -> None:
        gfa_text = """# This is a comment
H\tVN:Z:1.0
# Another comment
S\t1\tACGT
S\t2\tTGCA"""
        expected = """H\tVN:Z:1.0
S\t1\tACGT
S\t2\tTGCA"""
        assert strip_gfa_comments(gfa_text) == expected

    def test_no_comments(self) -> None:
        gfa_text = """H\tVN:Z:1.0
S\t1\tACGT"""
        assert strip_gfa_comments(gfa_text) == gfa_text

    def test_only_comments(self) -> None:
        gfa_text = """# Comment 1
# Comment 2
# Comment 3"""
        assert strip_gfa_comments(gfa_text) == ""

    def test_preserves_structure(self) -> None:
        """Ensure non-comment lines are preserved exactly."""
        gfa_text = """H\tVN:Z:1.0
S\t11\tACGT\tLN:i:4
L\t11\t+\t12\t+\t4M"""
        assert strip_gfa_comments(gfa_text) == gfa_text

    def test_empty_string(self) -> None:
        """Test with empty input."""
        assert strip_gfa_comments("") == ""

    def test_mixed_empty_lines(self) -> None:
        """Test that empty lines are removed."""
        gfa_text = """H\tVN:Z:1.0

S\t1\tACGT

S\t2\tTGCA"""
        expected = """H\tVN:Z:1.0
S\t1\tACGT
S\t2\tTGCA"""
        assert strip_gfa_comments(gfa_text) == expected
