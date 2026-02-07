#!/usr/bin/env python3
"""Utility functions for GFA file manipulation."""


def strip_gfa_comments(gfa_text: str) -> str:
    """
    Remove comment lines from GFA text.

    Comment lines start with '#' character. This function removes all such lines
    and any trailing empty lines, making it suitable for comparing GFA file content
    to to_gfa() output which doesn't include comments.

    :param gfa_text: GFA text content (may include comments)
    :return: GFA text with all comment lines removed

    Example:
        >>> original = "# Comment\\nH\\tVN:Z:1.0\\nS\\t1\\tACGT"
        >>> print(strip_gfa_comments(original))
        H\tVN:Z:1.0
        S\t1\tACGT
    """
    lines = []
    for line in gfa_text.split('\n'):
        # Skip comment lines and empty lines
        stripped = line.strip()
        if stripped and not stripped.startswith('#'):
            lines.append(line)

    return '\n'.join(lines)
