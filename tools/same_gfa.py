import argparse
import os
import sys

from networkx.algorithms.isomorphism import (
    MultiGraphMatcher,
    categorical_edge_match,
    categorical_node_match,
)

# Add the project root to the Python path to ensure imports work correctly
# Assuming the script is located in 'tools/' and 'pygfa/' is in the root
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from pygfa.gfa import GFA  # noqa: E402


def check_isomorphism(gfa1, gfa2):
    """Check if two GFA graphs are structurally isomorphic.

    This compares the graph topology ignoring node and edge IDs,
    but considering sequence, orientation, and other attributes.

    :param gfa1: First GFA object
    :param gfa2: Second GFA object
    :return: True if graphs are isomorphic, False otherwise
    """
    # Check basic graph properties first
    if gfa1.number_of_nodes() != gfa2.number_of_nodes():
        return False
    if gfa1.number_of_edges() != gfa2.number_of_edges():
        return False

    # Use networkx MultiGraphMatcher for isomorphism checking
    # Match nodes by sequence length (slen)
    # Match edges by alignment and orientation
    matcher = MultiGraphMatcher(
        gfa1._graph,
        gfa2._graph,
        node_match=categorical_node_match(["slen"], [None]),
        edge_match=categorical_edge_match(
            ["from_orn", "to_orn", "alignment"], [None, None, None]
        ),
    )

    return matcher.is_isomorphic()


def graphs_equal(gfa1, gfa2):
    """Check if two GFA graphs are equal (direct comparison).
    
    This uses the GFA.__eq__ method which compares graph elements directly.
    
    :param gfa1: First GFA object
    :param gfa2: Second GFA object
    :return: True if graphs are equal, False otherwise
    """
    return gfa1 == gfa2


def main():
    """
    Compares two GFA files to determine if they represent the same graph structure.
    
    By default, this checks both direct equality and graph isomorphism, returning
    True if either check passes. This means graphs with different GFA representations
    but identical structure will be considered equal.

    Usage: python same_gfa.py [-s|--strict] <file1.gfa> <file2.gfa>
    """
    parser = argparse.ArgumentParser(
        description="Compare two GFA files for structural equality."
    )
    parser.add_argument("file1", help="First GFA file")
    parser.add_argument("file2", help="Second GFA file")
    parser.add_argument(
        "-s",
        "--strict",
        action="store_true",
        help="Use strict comparison only (no isomorphism checking)",
    )
    parser.add_argument(
        "-i",
        "--isomorphic-only",
        action="store_true",
        help="Use only isomorphism checking (skip direct comparison)",
    )

    args = parser.parse_args()

    file1_path = args.file1
    file2_path = args.file2

    # Check if files exist
    if not os.path.exists(file1_path):
        print(f"Error: File not found: {file1_path}")
        sys.exit(1)
    if not os.path.exists(file2_path):
        print(f"Error: File not found: {file2_path}")
        sys.exit(1)

    try:
        # Load the first GFA file
        print(f"Loading {file1_path}...")
        gfa1 = GFA.from_file(file1_path)

        # Load the second GFA file
        print(f"Loading {file2_path}...")
        gfa2 = GFA.from_file(file2_path)

        # Compare the graphs based on mode
        if args.strict:
            # Strict mode: only direct comparison
            print("Using strict comparison...")
            if graphs_equal(gfa1, gfa2):
                print("Result: The graphs are equal.")
                sys.exit(0)
            else:
                print("Result: The graphs are different.")
                sys.exit(1)
        elif args.isomorphic_only:
            # Isomorphism only mode
            print("Using isomorphism checking...")
            if check_isomorphism(gfa1, gfa2):
                print("Result: The graphs are isomorphic (structurally equivalent).")
                sys.exit(0)
            else:
                print("Result: The graphs are NOT isomorphic.")
                sys.exit(1)
        else:
            # Default mode: try both, succeed if either passes
            print("Checking graph equality...")
            if graphs_equal(gfa1, gfa2):
                print("Result: The graphs are equal.")
                sys.exit(0)
            
            print("Direct comparison failed. Checking isomorphism...")
            if check_isomorphism(gfa1, gfa2):
                print("Result: The graphs are isomorphic (structurally equivalent).")
                sys.exit(0)
            else:
                print("Result: The graphs are different (not equal and not isomorphic).")
                sys.exit(1)

    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
