import sys
import os

# Add src to path
sys.path.append(os.getcwd())

from pygfa.gfa import GFA
from pygfa.bgfa import read_bgfa

from pygfa.graph_element.node import Node
from pygfa.graph_element.edge import Edge


def test_roundtrip_granular(tmp_path):
    g = GFA()
    g.add_node(Node("s1", "ACGT"))
    g.add_node(Node("s2", "TGCA"))
    g.add_edge(Edge(None, "s1", "+", "s2", "+", (0, 4), (0, 4), alignment="4M"))

    output_bgfa = str(tmp_path / "test_compliance.bgfa")

    # Use huffman for names and 2bit for sequences
    g.to_bgfa(
        output_bgfa, segment_names_enc="varint-huffman", sequences_enc="delta-2bit", link_cigars_enc="varint-huffman"
    )

    g2 = read_bgfa(output_bgfa)

    assert list(g2.nodes()) == ["s1", "s2"]
    assert g2.nodes(identifier="s1")["sequence"] == "ACGT"
    assert g2.nodes(identifier="s2")["sequence"] == "TGCA"

    edges = list(g2.edges(data=True))
    assert len(edges) == 1
    assert edges[0][2]["alignment"] == "4M"

    print("Basic roundtrip passed!")


def test_superstring_roundtrip(tmp_path):
    g = GFA()
    g.add_node(Node("s1", "GATTACA"))
    g.add_node(Node("s2", "TTACAGA"))

    output_bgfa = str(tmp_path / "test_superstring.bgfa")

    # Use superstring for sequences
    g.to_bgfa(output_bgfa, sequences_enc="varint-superstring_none")

    g2 = read_bgfa(output_bgfa)
    assert g2.nodes(identifier="s1")["sequence"] == "GATTACA"
    assert g2.nodes(identifier="s2")["sequence"] == "TTACAGA"

    print("Superstring roundtrip passed!")


def test_huffman_nibble_roundtrip(tmp_path):
    g = GFA()
    g.add_node(Node("s1", "ABCDEFGHIJKLMNOP"))  # Non-DNA to test Huffman properly

    output_bgfa = str(tmp_path / "test_huffman.bgfa")
    g.to_bgfa(output_bgfa, sequences_enc="varint-huffman")

    g2 = read_bgfa(output_bgfa)
    assert g2.nodes(identifier="s1")["sequence"] == "ABCDEFGHIJKLMNOP"
    print("Nibble-Huffman roundtrip passed!")


if __name__ == "__main__":
    import tempfile
    from pathlib import Path
    import shutil

    Path("results/test").mkdir(parents=True, exist_ok=True)
    tmp_dir = tempfile.mkdtemp(dir="results/test")
    try:
        test_roundtrip_granular(Path(tmp_dir))
        test_superstring_roundtrip(Path(tmp_dir))
        test_huffman_nibble_roundtrip(Path(tmp_dir))
        print("All compliance tests passed!")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
