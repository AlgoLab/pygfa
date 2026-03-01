import pytest
from pygfa.gfa import GFA
from pygfa.bgfa import ReaderBGFA
import tempfile
import os


def test_skip_payloads_basic():
    """Test basic skip_payloads functionality with a small BGFA file."""
    # Create a test BGFA file
    with tempfile.NamedTemporaryFile(suffix=".bgfa", delete=False) as f:
        test_file = f.name
        # Write minimal BGFA structure
        f.write(b"AFGB")  # Magic number
        f.write(struct.pack("<H", 1))  # Version
        f.write(struct.pack("<H", 10))  # Header length
        f.write(b"Test header\x00")  # Header text with null terminator

        # Segment names block (section_id=1)
        f.write(struct.pack("<B", 1))  # section_id
        f.write(struct.pack("<H", 2))  # record_num
        f.write(struct.pack("<H", 0x0000))  # compression_names (identity)
        f.write(struct.pack("<Q", 12))  # compressed_len
        f.write(struct.pack("<Q", 12))  # uncompressed_len
        f.write(b"seg1\x00seg2\x00")  # payload

        # Segments block (section_id=2)
        f.write(struct.pack("<B", 2))  # section_id
        f.write(struct.pack("<H", 2))  # record_num
        f.write(struct.pack("<H", 0x0000))  # compression_str (identity)
        f.write(struct.pack("<Q", 32))  # compressed_len
        f.write(struct.pack("<Q", 32))  # uncompressed_len
        f.write(struct.pack("<Q", 0))  # segment_id
        f.write(struct.pack("<Q", 4))  # sequence_length
        f.write(b"ACGT\x00")  # sequence
        f.write(struct.pack("<Q", 1))  # segment_id
        f.write(struct.pack("<Q", 4))  # sequence_length
        f.write(b"TTTT\x00")  # sequence

        # Links block (section_id=3)
        f.write(struct.pack("<B", 3))  # section_id
        f.write(struct.pack("<H", 1))  # record_num
        f.write(struct.pack("<H", 0x0000))  # compression_fromto (identity)
        f.write(struct.pack("<H", 0x0000))  # compression_cigars (identity)
        f.write(struct.pack("<Q", 24))  # compressed_len
        f.write(struct.pack("<Q", 24))  # uncompressed_len
        f.write(struct.pack("<Q", 0))  # from_id
        f.write(struct.pack("<Q", 1))  # to_id
        f.write(b"\x00\x00")  # orientations (both '+')
        f.write(b"2M\x00")  # CIGAR

        # Paths block (section_id=4)
        f.write(struct.pack("<B", 4))  # section_id
        f.write(struct.pack("<H", 1))  # record_num
        f.write(struct.pack("<H", 0x0000))  # compression_names (identity)
        f.write(struct.pack("<H", 0x0000))  # compression_paths (identity)
        f.write(struct.pack("<H", 0x0000))  # compression_cigars (identity)
        f.write(struct.pack("<Q", 16))  # compressed_len
        f.write(struct.pack("<Q", 16))  # uncompressed_len
        f.write(b"path1\x00")  # path name
        f.write(b"0,1\x00")  # segment list
        f.write(b"2M\x00")  # CIGAR

        # Walks block (section_id=5)
        f.write(struct.pack("<B", 5))  # section_id
        f.write(struct.pack("<H", 1))  # record_num
        f.write(struct.pack("<H", 0x0000))  # compression_sample_ids (identity)
        f.write(struct.pack("<H", 0x0000))  # compression_hap_indices (identity)
        f.write(struct.pack("<H", 0x0000))  # compression_seq_ids (identity)
        f.write(struct.pack("<H", 0x0000))  # compression_start (identity)
        f.write(struct.pack("<H", 0x0000))  # compression_end (identity)
        f.write(struct.pack("<H", 0x0000))  # compression_walks (identity)
        f.write(struct.pack("<Q", 32))  # compressed_len
        f.write(struct.pack("<Q", 32))  # uncompressed_len
        f.write(b"sample1\x00")  # sample_id
        f.write(struct.pack("<Q", 0))  # hap_index
        f.write(b"seq1\x00")  # seq_id
        f.write(struct.pack("<Q", 0))  # start
        f.write(struct.pack("<Q", 10))  # end
        f.write(b"0,1\x00")  # walk

    try:
        reader = ReaderBGFA()

        # Test with skip_payloads=False (full reading)
        gfa_full = reader.read_bgfa(test_file, skip_payloads=False)
        assert len(gfa_full.nodes()) == 2
        assert len(gfa_full.edges()) == 1
        assert len(gfa_full.paths()) == 1
        assert len(gfa_full.walks()) == 1

        # Test with skip_payloads=True (header only)
        gfa_skip = reader.read_bgfa(test_file, skip_payloads=True)
        assert len(gfa_skip.nodes()) == 0
        assert len(gfa_skip.edges()) == 0
        assert len(gfa_skip.paths()) == 0
        assert len(gfa_skip.walks()) == 0

        # Verify that header was read correctly
        assert gfa_skip._header_info["version"] == 1
        assert gfa_skip._header_info["header_text"] == "Test header"

    finally:
        os.unlink(test_file)


def test_skip_payloads_multiple_blocks():
    """Test skip_payloads with multiple blocks of different types."""
    with tempfile.NamedTemporaryFile(suffix=".bgfa", delete=False) as f:
        test_file = f.name

        # Write BGFA with multiple blocks
        f.write(b"AFGB")  # Magic number
        f.write(struct.pack("<H", 1))  # Version
        f.write(struct.pack("<H", 5))  # Header length
        f.write(b"Test\x00")  # Header text with null terminator

        # Multiple segment names blocks
        for i in range(3):
            f.write(struct.pack("<B", 1))  # section_id
            f.write(struct.pack("<H", 2))  # record_num
            f.write(struct.pack("<H", 0x0000))  # compression_names (identity)
            f.write(struct.pack("<Q", 12))  # compressed_len
            f.write(struct.pack("<Q", 12))  # uncompressed_len
            f.write(b"seg1\x00seg2\x00")  # payload

        # Multiple segments blocks
        for i in range(2):
            f.write(struct.pack("<B", 2))  # section_id
            f.write(struct.pack("<H", 2))  # record_num
            f.write(struct.pack("<H", 0x0000))  # compression_str (identity)
            f.write(struct.pack("<Q", 32))  # compressed_len
            f.write(struct.pack("<Q", 32))  # uncompressed_len
            f.write(struct.pack("<Q", 0))  # segment_id
            f.write(struct.pack("<Q", 4))  # sequence_length
            f.write(b"ACGT\x00")  # sequence
            f.write(struct.pack("<Q", 1))  # segment_id
            f.write(struct.pack("<Q", 4))  # sequence_length
            f.write(b"TTTT\x00")  # sequence

        # Multiple links blocks
        for i in range(2):
            f.write(struct.pack("<B", 3))  # section_id
            f.write(struct.pack("<H", 1))  # record_num
            f.write(struct.pack("<H", 0x0000))  # compression_fromto (identity)
            f.write(struct.pack("<H", 0x0000))  # compression_cigars (identity)
            f.write(struct.pack("<Q", 24))  # compressed_len
            f.write(struct.pack("<Q", 24))  # uncompressed_len
            f.write(struct.pack("<Q", 0))  # from_id
            f.write(struct.pack("<Q", 1))  # to_id
            f.write(b"\x00\x00")  # orientations (both '+')
            f.write(b"2M\x00")  # CIGAR

        # Multiple paths blocks
        for i in range(2):
            f.write(struct.pack("<B", 4))  # section_id
            f.write(struct.pack("<H", 1))  # record_num
            f.write(struct.pack("<H", 0x0000))  # compression_names (identity)
            f.write(struct.pack("<H", 0x0000))  # compression_paths (identity)
            f.write(struct.pack("<H", 0x0000))  # compression_cigars (identity)
            f.write(struct.pack("<Q", 16))  # compressed_len
            f.write(struct.pack("<Q", 16))  # uncompressed_len
            f.write(b"path1\x00")  # path name
            f.write(b"0,1\x00")  # segment list
            f.write(b"2M\x00")  # CIGAR

        # Multiple walks blocks
        for i in range(2):
            f.write(struct.pack("<B", 5))  # section_id
            f.write(struct.pack("<H", 1))  # record_num
            f.write(struct.pack("<H", 0x0000))  # compression_sample_ids (identity)
            f.write(struct.pack("<H", 0x0000))  # compression_hap_indices (identity)
            f.write(struct.pack("<H", 0x0000))  # compression_seq_ids (identity)
            f.write(struct.pack("<H", 0x0000))  # compression_start (identity)
            f.write(struct.pack("<H", 0x0000))  # compression_end (identity)
            f.write(struct.pack("<H", 0x0000))  # compression_walks (identity)
            f.write(struct.pack("<Q", 32))  # compressed_len
            f.write(struct.pack("<Q", 32))  # uncompressed_len
            f.write(b"sample1\x00")  # sample_id
            f.write(struct.pack("<Q", 0))  # hap_index
            f.write(b"seq1\x00")  # seq_id
            f.write(struct.pack("<Q", 0))  # start
            f.write(struct.pack("<Q", 10))  # end
            f.write(b"0,1\x00")  # walk

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
        assert gfa_skip._header_info["header_text"] == "Test"

        # Test with skip_payloads=False (full reading)
        gfa_full = reader.read_bgfa(test_file, skip_payloads=False)

        # Should read all data
        # 3 segment names blocks * 2 segments each = 6 nodes
        # 2 links blocks * 1 link each = 2 edges
        # 2 paths blocks * 1 path each = 2 paths
        # 2 walks blocks * 1 walk each = 2 walks
        assert len(gfa_full.nodes()) == 6
        assert len(gfa_full.edges()) == 2
        assert len(gfa_full.paths()) == 2
        assert len(gfa_full.walks()) == 2

    finally:
        os.unlink(test_file)


def test_skip_payloads_invalid_header():
    """Test skip_payloads with invalid header scenarios."""
    with tempfile.NamedTemporaryFile(suffix=".bgfa", delete=False) as f:
        test_file = f.name

        # Write invalid BGFA (missing magic number)
        f.write(b"NOTAFGB")  # Invalid magic number
        f.write(struct.pack("<H", 1))  # Version
        f.write(struct.pack("<H", 5))  # Header length
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
    """Test skip_payloads with partial/corrupted files."""
    with tempfile.NamedTemporaryFile(suffix=".bgfa", delete=False) as f:
        test_file = f.name

        # Write incomplete BGFA
        f.write(b"AFGB")  # Magic number
        f.write(struct.pack("<H", 1))  # Version
        f.write(struct.pack("<H", 5))  # Header length
        f.write(b"Test\x00")  # Header text with null terminator

        # Add one complete block
        f.write(struct.pack("<B", 1))  # section_id
        f.write(struct.pack("<H", 2))  # record_num
        f.write(struct.pack("<H", 0x0000))  # compression_names (identity)
        f.write(struct.pack("<Q", 12))  # compressed_len
        f.write(struct.pack("<Q", 12))  # uncompressed_len
        f.write(b"seg1\x00seg2\x00")  # payload

        # Add incomplete block (missing payload)
        f.write(struct.pack("<B", 2))  # section_id
        f.write(struct.pack("<H", 2))  # record_num
        f.write(struct.pack("<H", 0x0000))  # compression_str (identity)
        f.write(struct.pack("<Q", 32))  # compressed_len
        f.write(struct.pack("<Q", 32))  # uncompressed_len
        # Missing payload data

    try:
        reader = ReaderBGFA()

        # Test with skip_payloads=True (should handle partial file gracefully)
        gfa_skip = reader.read_bgfa(test_file, skip_payloads=True)
        assert len(gfa_skip.nodes()) == 0
        assert len(gfa_skip.edges()) == 0
        assert len(gfa_skip.paths()) == 0
        assert len(gfa_skip.walks()) == 0

        # Verify header was read correctly
        assert gfa_skip._header_info["version"] == 1
        assert gfa_skip._header_info["header_text"] == "Test"

        # Test with skip_payloads=False (should fail on incomplete block)
        with pytest.raises(ValueError, match="BGFA file is too short"):
            reader.read_bgfa(test_file, skip_payloads=False)

    finally:
        os.unlink(test_file)


def test_skip_payloads_empty_file():
    """Test skip_payloads with empty/very small files."""
    with tempfile.NamedTemporaryFile(suffix=".bgfa", delete=False) as f:
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
    with tempfile.NamedTemporaryFile(suffix=".bgfa", delete=False) as f:
        test_file = f.name

        # Write minimal BGFA with only header
        f.write(b"AFGB")  # Magic number
        f.write(struct.pack("<H", 1))  # Version
        f.write(struct.pack("<H", 5))  # Header length
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
    with tempfile.NamedTemporaryFile(suffix=".bgfa", delete=False) as f:
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

        # Verify nodes match
        nodes_full = {n.nid: n for n in gfa_full.nodes()}
        assert "seg1" in nodes_full
        assert "seg2" in nodes_full

        # Verify header was read correctly
        assert gfa_full._header_info["version"] == 1

    finally:
        os.unlink(bgfa_path)
