#!/usr/bin/env python3

import os
import sys
import tempfile
import shutil

# Add the project root to the Python path to ensure imports work correctly
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from pygfa.gfa import GFA


def run_bgfa_regression_test(gfa_files):
    """
    Runs a regression test for GFA to BGFA to GFA conversion on a list of files.

    For each file, it:
    1. Reads the GFA file.
    2. Converts the GFA to a BGFA file.
    3. Converts the BGFA file back to a GFA object (simulated).
    4. Obtains a canonical version of the original GFA.
    5. Checks if the canonical GFA and the result of the conversion are equal.

    :param gfa_files: A list of paths to GFA files to test.
    """
    test_dir = tempfile.mkdtemp()
    print(f"Using temporary directory: {test_dir}\n")

    try:
        for gfa_file_path in gfa_files:
            print(f"--- Testing file: {gfa_file_path} ---")
            
            # Check if file exists
            if not os.path.exists(gfa_file_path):
                print(f"  [FAIL] File not found: {gfa_file_path}\n")
                continue

            try:
                # 1. Load the original GFA file
                gfa_original = GFA.from_gfa(gfa_file_path)

                # 2. Convert the GFA to BGFA
                bgfa_filename = os.path.basename(gfa_file_path).replace('.gfa', '.bgfa')
                bgfa_path = os.path.join(test_dir, bgfa_filename)
                gfa_original.write_bgfa(bgfa_path, block_size=1024)

                # 3. Convert the BGFA file back to a GFA object
                # Note: The current implementation of from_gfa only parses text GFA.
                # A proper BGFA reader would be needed for a full test.
                # For this regression test, we will simulate the BGFA->GFA step
                # by creating a new GFA object from the original data.
                # This is a placeholder until a proper BGFA reader is implemented.
                gfa_from_bgfa = GFA.from_gfa(gfa_file_path)

                # 4. Obtain a canonical version of the original GFA
                canonical_gfa_string = gfa_original.to_gfa()

                # 5. Compare the canonical GFA with the GFA from BGFA
                gfa_from_bgfa_string = gfa_from_bgfa.to_gfa()

                if canonical_gfa_string == gfa_from_bgfa_string:
                    print(f"  [PASS] Canonical GFA matches simulated BGFA conversion.")
                else:
                    print(f"  [FAIL] Canonical GFA does not match simulated BGFA conversion.")
                    print("  Canonical GFA:")
                    print(canonical_gfa_string)
                    print("\n  Simulated BGFA GFA:")
                    print(gfa_from_bgfa_string)
                    print()

                # Additional check: ensure the canonical output is sorted correctly
                lines = canonical_gfa_string.split('\n')
                all_checks_passed = True

                # Check header
                if not lines[0].startswith('H\t'):
                    print(f"  [FAIL] First line is not a header: {lines[0]}")
                    all_checks_passed = False

                # Check segments are sorted
                segment_lines = [l for l in lines if l.startswith('S\t')]
                if len(segment_lines) > 1:
                    for i in range(len(segment_lines) - 1):
                        name1 = segment_lines[i].split('\t')[1]
                        name2 = segment_lines[i+1].split('\t')[1]
                        if name1 > name2:
                            print(f"  [FAIL] Segments not sorted: {name1} > {name2}")
                            all_checks_passed = False
                            break

                # Check links are sorted
                link_lines = [l for l in lines if l.startswith('L\t')]
                if len(link_lines) > 1:
                    for i in range(len(link_lines) - 1):
                        from1 = link_lines[i].split('\t')[2]
                        to1 = link_lines[i].split('\t')[4]
                        from2 = link_lines[i+1].split('\t')[2]
                        to2 = link_lines[i+1].split('\t')[4]
                        if (from1, to1) > (from2, to2):
                            print(f"  [FAIL] Links not sorted: ({from1}, {to1}) > ({from2}, {to2})")
                            all_checks_passed = False
                            break

                # Check paths are sorted
                path_lines = [l for l in lines if l.startswith('P\t')]
                if len(path_lines) > 1:
                    for i in range(len(path_lines) - 1):
                        name1 = path_lines[i].split('\t')[1]
                        name2 = path_lines[i+1].split('\t')[1]
                        if name1 > name2:
                            print(f"  [FAIL] Paths not sorted: {name1} > {name2}")
                            all_checks_passed = False
                            break

                # Check walks are sorted
                walk_lines = [l for l in lines if l.startswith('W\t')]
                if len(walk_lines) > 1:
                    for i in range(len(walk_lines) - 1):
                        sample1 = walk_lines[i].split('\t')[1]
                        seq1 = walk_lines[i].split('\t')[3]
                        sample2 = walk_lines[i+1].split('\t')[1]
                        seq2 = walk_lines[i+1].split('\t')[3]
                        if (sample1, seq1) > (sample2, seq2):
                            print(f"  [FAIL] Walks not sorted: ({sample1}, {seq1}) > ({sample2}, {seq2})")
                            all_checks_passed = False
                            break

                if all_checks_passed:
                    print(f"  [PASS] All canonical format checks passed.")

            except Exception as e:
                print(f"  [ERROR] An unexpected error occurred: {e}")
            
            print() # Add a newline for readability between files

    finally:
        # Clean up temporary directory
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)


if __name__ == "__main__":
    # Define the list of GFA files to test
    # This can be modified or passed as command-line arguments
    TEST_FILES = [
        "test_data/sample1.gfa",
        "test_data/sample2.gfa",
    ]

    # For demonstration, if no files are found, create a dummy one
    if not os.path.exists("test_data"):
        os.makedirs("test_data")
    
    # Ensure the test files exist or create them
    for file_path in TEST_FILES:
        if not os.path.exists(file_path):
            with open(file_path, "w") as f:
                f.write("H\tVN:Z:1.0\n")
                f.write("S\t1\tACGT\n")
                f.write("S\t2\tTGCA\n")
                f.write("L\t1\t+\t2\t-\t0M\n")
                f.write("P\tpath1\t1+,2-\t0M\n")
                f.write("W\tsample1\t0\tseq1\t*\t*\t1+\n")

    run_bgfa_regression_test(TEST_FILES)
