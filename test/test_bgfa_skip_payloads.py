import pytest
from pygfa.gfa import GFA
from pygfa.bgfa import ReaderBGFA
from pygfa.graph_element import node
import tempfile
import os
import struct

_test_output_dir = os.path.join("results", "test", "bgfa_skip_payloads")
os.makedirs(_test_output_dir, exist_ok=True)


def test_skip_payloads_basic():
    """Test basic skip_payloads functionality with a small BGFA file."""
    # Create a GFA and write it to BGFA format to ensure correct format
    g = GFA()
    n1 = node.Node("seg1", "ACGT", 4)
    n2 = node.Node("seg2", "TTTT", 4)
    g.add_node(n1)
    g.add_node(n2)

    with tempfile.NamedTemporaryFile(suffix=".bgfa", delete=False, dir=_test_output_dir) as f:
        test_file = f.name
        # Use the actual writer to create a properly formatted BGFA file
        g.to_bgfa(test_file, block_size=1024, compression_options=None, verbose=False, debug=False, logfile=None)

    try:
        reader = ReaderBGFA()

        # Test with skip_payloads=False (full reading)
        gfa_full = reader.read_bgfa(test_file, skip_payloads=False)
        assert len(gfa_full.nodes()) == 2
        assert len(gfa_full.edges()) == 0  # No edges in this simple graph

        # Test with skip_payloads=True (header only)
        gfa_skip = reader.read_bgfa(test_file, skip_payloads=True)
        assert len(gfa_skip.nodes()) == 0
        assert len(gfa_skip.edges()) == 0
        assert len(gfa_skip.paths()) == 0
        assert len(gfa_skip.walks()) == 0

        # Verify that header was read correctly
        assert gfa_skip._header_info["version"] == 1

    finally:
        os.unlink(test_file)


def test_skip_payloads_multiple_blocks():
    """Test skip_payloads with a BGFA file created by the writer."""
    # Create a GFA with multiple nodes and edges
    g = GFA()
    for i in range(6):
        g.add_node(node.Node(f"seg{i}", "ACGT", 4))

    with tempfile.NamedTemporaryFile(suffix=".bgfa", delete=False, dir=_test_output_dir) as f:
        test_file = f.name
        # Use small block_size to create multiple blocks
        g.to_bgfa(test_file, block_size=2, compression_options=None, verbose=False, debug=False, logfile=None)

    try:
        reader = ReaderBGFA()

        # Test with skip_payloads=True
        gfa_skip = reader.read_bgfa(test_file, skip_payloads=True)

        # Should read header but skip all payloads
        assert len(gfa_skip.nodes()) == 0
        assert len(gfa_skip.edges()) == 0
        assert len(gfa_skip.paths()) == 0
        assert len(gfa_skip.walks()) == 0

        # Verify header was read correctly
        assert gfa_skip._header_info["version"] == 1

        # Test with skip_payloads=False (full reading)
        gfa_full = reader.read_bgfa(test_file, skip_payloads=False)

        # Should read all data
        assert len(gfa_full.nodes()) == 6

    finally:
        os.unlink(test_file)


def test_skip_payloads_invalid_header():
    """Test skip_payloads with invalid header scenarios."""
    with tempfile.NamedTemporaryFile(suffix=".bgfa", delete=False, dir=_test_output_dir) as f:
        test_file = f.name

        # Write invalid BGFA (missing magic number)
        f.write(b"NOTA")  # Invalid magic number
        f.write(struct.pack("<H", 1))  # Version
        f.write(struct.pack("<H", 4))  # Header length
        f.write(b"Test\x00")  # Header text with null terminator

        # Add some blocks
        f.write(struct.pack("<B", 1))  # section_id
        f.write(struct.pack("<H", 2))  # record_num
        f.write(struct.pack("<H", 0x0000))  # compression_names (identity)
        f.write(struct.pack("<Q", 12))  # compressed_len
        f.write(struct.pack("<Q", 12))  # uncompressed_len
        f.write(b"seg1\x00seg2\x00")  # payload

    try:
        reader = ReaderBGFA()

        # Test with skip_payloads=True (should still fail on invalid magic number)
        with pytest.raises(ValueError, match="Invalid magic number"):
            reader.read_bgfa(test_file, skip_payloads=True)

        # Test with skip_payloads=False (should also fail on invalid magic number)
        with pytest.raises(ValueError, match="Invalid magic number"):
            reader.read_bgfa(test_file, skip_payloads=False)

    finally:
        os.unlink(test_file)


def test_skip_payloads_partial_file():
    """Test skip_payloads with a truncated file."""
    # Create a valid BGFA file first
    g = GFA()
    g.add_node(node.Node("seg1", "ACGT", 4))

    with tempfile.NamedTemporaryFile(suffix=".bgfa", delete=False, dir=_test_output_dir) as f:
        complete_file = f.name
        g.to_bgfa(complete_file, block_size=1024, compression_options=None, verbose=False, debug=False, logfile=None)

    # Read the complete file and truncate it
    with open(complete_file, "rb") as f:
        data = f.read()

    # Truncate in the middle of a block
    truncated_data = data[: len(data) // 2]

    with tempfile.NamedTemporaryFile(suffix=".bgfa", delete=False, dir=_test_output_dir) as f:
        test_file = f.name
        f.write(truncated_data)

    os.unlink(complete_file)

    try:
        reader = ReaderBGFA()

        # Test with skip_payloads=True - should handle truncated file gracefully
        # by reading header and skipping incomplete blocks
        gfa_skip = reader.read_bgfa(test_file, skip_payloads=True)
        assert len(gfa_skip.nodes()) == 0  # Should have skipped payloads

        # Verify header was read correctly (if file has valid header)
        if len(truncated_data) >= 8:  # At least magic + version
            assert gfa_skip._header_info["version"] == 1

    finally:
        os.unlink(test_file)


def test_skip_payloads_empty_file():
    """Test skip_payloads with empty/very small files."""
    with tempfile.NamedTemporaryFile(suffix=".bgfa", delete=False, dir=_test_output_dir) as f:
        test_file = f.name

        # Empty file
        pass

    try:
        reader = ReaderBGFA()

        # Test with skip_payloads=True (empty file)
        with pytest.raises(ValueError, match="BGFA file is too short"):
            reader.read_bgfa(test_file, skip_payloads=True)

        # Test with skip_payloads=False (empty file)
        with pytest.raises(ValueError, match="BGFA file is too short"):
            reader.read_bgfa(test_file, skip_payloads=False)

    finally:
        os.unlink(test_file)


def test_skip_payloads_minimal():
    """Test skip_payloads with minimal valid BGFA file."""
    with tempfile.NamedTemporaryFile(suffix=".bgfa", delete=False, dir=_test_output_dir) as f:
        test_file = f.name

        # Write minimal BGFA with only header
        f.write(b"BGFA")  # Magic number (0x41464742 in little-endian)
        f.write(struct.pack("<H", 1))  # Version
        f.write(struct.pack("<H", 4))  # Header length (length of "Test", excluding null terminator)
        f.write(b"Test\x00")  # Header text with null terminator

    try:
        reader = ReaderBGFA()

        # Test with skip_payloads=True (minimal file)
        gfa_skip = reader.read_bgfa(test_file, skip_payloads=True)
        assert len(gfa_skip.nodes()) == 0
        assert len(gfa_skip.edges()) == 0
        assert len(gfa_skip.paths()) == 0
        assert len(gfa_skip.walks()) == 0

        # Verify header was read correctly
        assert gfa_skip._header_info["version"] == 1
        assert gfa_skip._header_info["header_text"] == "Test"

        # Test with skip_payloads=False (minimal file)
        gfa_full = reader.read_bgfa(test_file, skip_payloads=False)
        assert len(gfa_full.nodes()) == 0
        assert len(gfa_full.edges()) == 0
        assert len(gfa_full.paths()) == 0
        assert len(gfa_full.walks()) == 0

        # Verify header was read correctly
        assert gfa_full._header_info["version"] == 1
        assert gfa_full._header_info["header_text"] == "Test"

    finally:
        os.unlink(test_file)


def test_skip_payloads_with_existing_gfa():
    """Test skip_payloads in context of existing GFA functionality."""
    # Create a simple GFA graph
    g = GFA()
    n1 = node.Node("seg1", "ACGT", 4)
    n2 = node.Node("seg2", "TTTT", 4)
    g.add_node(n1)
    g.add_node(n2)

    # Convert to BGFA and back with skip_payloads
    with tempfile.NamedTemporaryFile(suffix=".bgfa", delete=False, dir=_test_output_dir) as f:
        bgfa_path = f.name

        # Write GFA to BGFA with full data
        g.to_bgfa(bgfa_path, block_size=1024, compression_options=None, verbose=False, debug=False, logfile=None)

    try:
        reader = ReaderBGFA()

        # Read with skip_payloads=True (should get empty graph)
        gfa_skip = reader.read_bgfa(bgfa_path, skip_payloads=True)
        assert len(gfa_skip.nodes()) == 0
        assert len(gfa_skip.edges()) == 0
        assert len(gfa_skip.paths()) == 0
        assert len(gfa_skip.walks()) == 0

        # Read with skip_payloads=False (should get full graph)
        gfa_full = reader.read_bgfa(bgfa_path, skip_payloads=False)
        assert len(gfa_full.nodes()) == 2
        assert len(gfa_full.edges()) == 0  # No edges in this simple example

        # Verify nodes match - nodes() returns node IDs (strings)
        nodes_full = list(gfa_full.nodes())
        assert "seg1" in nodes_full
        assert "seg2" in nodes_full

        # Verify header was read correctly
        assert gfa_full._header_info["version"] == 1

    finally:
        os.unlink(bgfa_path)
