import sys
import os

# Add src to path
sys.path.append(os.getcwd())

from pygfa.gfa import GFA
from pygfa.bgfa import read_bgfa

from pygfa.graph_element.node import Node
from pygfa.graph_element.edge import Edge


def test_roundtrip_granular():
    g = GFA()
    g.add_node(Node("s1", "ACGT"))
    g.add_node(Node("s2", "TGCA"))
    g.add_edge(Edge(None, "s1", "+", "s2", "+", (0, 4), (0, 4), alignment="4M"))

    output_bgfa = "test_compliance.bgfa"

    # Use huffman for names and 2bit for sequences
    g.to_bgfa(output_bgfa, names_enc="varint-huffman", seq_enc="delta-2bit", links_cigars_enc="varint-huffman")

    g2 = read_bgfa(output_bgfa)

    assert list(g2.nodes()) == ["s1", "s2"]
    assert g2.nodes(identifier="s1")["sequence"] == "ACGT"
    assert g2.nodes(identifier="s2")["sequence"] == "TGCA"

    edges = list(g2.edges(data=True))
    assert len(edges) == 1
    assert edges[0][2]["alignment"] == "4M"

    print("Basic roundtrip passed!")


def test_superstring_roundtrip():
    g = GFA()
    g.add_node(Node("s1", "GATTACA"))
    g.add_node(Node("s2", "TTACAGA"))

    output_bgfa = "test_superstring.bgfa"

    # Use superstring for sequences
    g.to_bgfa(output_bgfa, seq_enc="varint-superstring_none")

    g2 = read_bgfa(output_bgfa)
    assert g2.nodes(identifier="s1")["sequence"] == "GATTACA"
    assert g2.nodes(identifier="s2")["sequence"] == "TTACAGA"

    print("Superstring roundtrip passed!")


def test_huffman_nibble_roundtrip():
    g = GFA()
    g.add_node(Node("s1", "ABCDEFGHIJKLMNOP"))  # Non-DNA to test Huffman properly

    output_bgfa = "test_huffman.bgfa"
    g.to_bgfa(output_bgfa, seq_enc="varint-huffman")

    g2 = read_bgfa(output_bgfa)
    assert g2.nodes(identifier="s1")["sequence"] == "ABCDEFGHIJKLMNOP"
    print("Nibble-Huffman roundtrip passed!")


if __name__ == "__main__":
    try:
        test_roundtrip_granular()
        test_superstring_roundtrip()
        test_huffman_nibble_roundtrip()
        print("All compliance tests passed!")
    finally:
        for f in ["test_compliance.bgfa", "test_superstring.bgfa", "test_huffman.bgfa"]:
            if os.path.exists(f):
                os.remove(f)
