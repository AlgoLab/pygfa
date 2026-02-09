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
    Compares two GFA files to determine if they represent the same graph structure,
    ignoring differences in element IDs.

    Usage: python same_gfa.py <file1.gfa> <file2.gfa>
    """
    if len(sys.argv) != 3:
        print("Usage: python same_gfa.py <file1.gfa> <file2.gfa>")
        sys.exit(1)

    file1_path = sys.argv[1]
    file2_path = sys.argv[2]

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

        # Compare the graphs
        # The GFA.__eq__ method is designed to handle ID differences
        # and check structural equality.
        if gfa1 == gfa2:
            print("Result: The graphs are the same (ignoring element IDs).")
            sys.exit(0)
        else:
            print("Result: The graphs are different.")
            sys.exit(1)

    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
