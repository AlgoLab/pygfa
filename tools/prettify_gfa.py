#!/usr/bin/env python3
"""
Prettify GFA file

This program reads a GFA file and pretty prints the resulting graph
using the GFA.pprint() method.
"""

import sys
import os

# Add the project root to the Python path to ensure imports work correctly
# Assuming the script is located in 'tools/' and 'pygfa/' is in the root
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from pygfa.gfa import GFA  # noqa: E402


def main():
    """
    Reads a GFA file and pretty prints the resulting graph.

    Usage: python prettify_gfa.py <file.gfa>
    """
    if len(sys.argv) != 2:
        print("Usage: python prettify_gfa.py <file.gfa>")
        sys.exit(1)

    file_path = sys.argv[1]

    # Check if file exists
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        sys.exit(1)

    try:
        # Load the GFA file
        print(f"Loading {file_path}...")
        gfa = GFA.from_gfa(file_path)

        # Pretty print the graph
        gfa.pprint()

    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
