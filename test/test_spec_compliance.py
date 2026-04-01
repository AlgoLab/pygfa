import os
import sys
import tempfile

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from pygfa.gfa import GFA  # noqa: E402
from pygfa.bgfa import read_bgfa  # noqa: E402

from pygfa.graph_element.node import Node  # noqa: E402
from pygfa.graph_element.edge import Edge  # noqa: E402


def test_roundtrip_granular():
    g = GFA()
    g.add_node(Node("s1", "ACGT"))
    g.add_node(Node("s2", "TGCA"))
    g.add_edge(Edge(None, "s1", "+", "s2", "+", (0, 4), (0, 4), alignment="4M"))

    output_bgfa = tempfile.mktemp(suffix=".bgfa")

    g.to_bgfa(
        output_bgfa,
        names_enc="varint-huffman",
        seq_enc="delta-2bit",
        links_cigars_enc="varint-huffman",
    )

    g2 = read_bgfa(output_bgfa)

    assert list(g2.nodes()) == ["s1", "s2"]
    assert g2.nodes(identifier="s1")["sequence"] == "ACGT"
    assert g2.nodes(identifier="s2")["sequence"] == "TGCA"

    edges = list(g2.edges(data=True))
    assert len(edges) == 1
    assert edges[0][2]["alignment"] == "4M"

    print("Basic roundtrip passed!")

    if os.path.exists(output_bgfa):
        os.remove(output_bgfa)


def test_superstring_roundtrip():
    g = GFA()
    g.add_node(Node("s1", "GATTACA"))
    g.add_node(Node("s2", "TTACAGA"))

    output_bgfa = tempfile.mktemp(suffix=".bgfa")

    g.to_bgfa(output_bgfa, seq_enc="varint-superstring_none")

    g2 = read_bgfa(output_bgfa)
    assert g2.nodes(identifier="s1")["sequence"] == "GATTACA"
    assert g2.nodes(identifier="s2")["sequence"] == "TTACAGA"

    print("Superstring roundtrip passed!")

    if os.path.exists(output_bgfa):
        os.remove(output_bgfa)


def test_huffman_nibble_roundtrip():
    g = GFA()
    g.add_node(Node("s1", "ABCDEFGHIJKLMNOP"))

    output_bgfa = tempfile.mktemp(suffix=".bgfa")
    g.to_bgfa(output_bgfa, seq_enc="varint-huffman")

    g2 = read_bgfa(output_bgfa)
    assert g2.nodes(identifier="s1")["sequence"] == "ABCDEFGHIJKLMNOP"
    print("Nibble-Huffman roundtrip passed!")

    if os.path.exists(output_bgfa):
        os.remove(output_bgfa)


if __name__ == "__main__":
    test_roundtrip_granular()
    test_superstring_roundtrip()
    test_huffman_nibble_roundtrip()
    print("All compliance tests passed!")
