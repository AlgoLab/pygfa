#!/usr/bin/env python3

import os
import subprocess
import sys
import tempfile
import shutil
import pytest
import glob

# Add the project root to the Python path to ensure imports work correctly
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from pygfa.gfa import GFA


# Dynamically find all .gfa files in the test directory
# This will match files like test/sample1.gfa, test/sample2.gfa, etc.
TEST_FILES = glob.glob("test/*.gfa")


@pytest.fixture(scope="module")
def temp_dir():
    """Create a temporary directory for test files."""
    test_dir = tempfile.mkdtemp()
    yield test_dir
    # Clean up temporary directory after tests
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)


@pytest.fixture(scope="module", params=TEST_FILES)
def gfa_file_path(request):
    """Provide the path to a GFA file for testing."""
    file_path = request.param
    
    # Check if file exists (it should, since glob found it)
    if not os.path.exists(file_path):
        pytest.skip(f"Test file not found: {file_path}")
    
    return file_path


def test_gfa_to_bgfa_to_gfa_regression(gfa_file_path):
    """
    Regression test that receives a gfa filename and:
    1. reads the gfa file to obtain a graph g
    2. writes the graph g to a bgfa file
    3. reads the bgfa file to obtain a graph h
    4. runs pprint on both g and h and checks if the outputs are the same
    5. if the outputs are not the same, both are saved in two separate files
    """
    print(f"\n--- Testing file: {gfa_file_path} ---")

    # 1. Load the original GFA file
    g = GFA.from_gfa(gfa_file_path)

    # 2. write the graph g to a bgfa file
    bgfa_filename = os.path.basename(gfa_file_path).replace(".gfa", ".bgfa")
    bgfa_path = os.path.join(bgfa_filename)
    g.write_bgfa(bgfa_path)

    # 3. read the bgfa file to obtain a graph h
    h = GFA()
    h.read_bgfa(bgfa_path)

    # 4. runs pprint on both g and h and checks if the outputs are the same
    g_pprint = g.pprint()
    h_pprint = h.pprint()
    
    if g_pprint != h_pprint:
        # 5. if the outputs are not the same, both are saved in two separate files
        with open("g_pprint.txt", "w") as f:
            f.write(g_pprint)
        with open("h_pprint.txt", "w") as f:
            f.write(h_pprint)
        assert False, "Pprint outputs are not the same"
    else:
        print("Pprint outputs are the same")

def test_bgfa_idempotent_1():
    """Test that pprint output matches expected file content."""
    test_gfa_to_bgfa_to_gfa_regression("data/example_1.gfa")

def test_bgfa_idempotent_2():
    """Test that pprint output matches expected file content."""
    test_gfa_to_bgfa_to_gfa_regression("data/example_2.gfa")

def test_bgfa_idempotent_3():
    """Test that pprint output matches expected file content."""
    test_gfa_to_bgfa_to_gfa_regression("data/example_3.gfa")


if __name__ == "__main__":
    # Run the tests using pytest
    pytest.main([__file__, "-v"])
