import os
import sys
import unittest

sys.path.insert(0, "../")

import pygfa
from test_utils import should_run_test_for_gfa

#
# --- = dovetail overlap
# ~~~ = other overlap
#
#
# [s1_s1] --- [s2_s2] --- [s3_s3] ~~
#                                  ~~~ [s4_s4] --- [s5_s5]
#
#
# [s6_s6] --- [s7_s7]                [s8_s8_s8]
#

GFA_FILE = os.path.join(os.path.dirname(__file__), "data", "test_gfa_operations.gfa")


class TestLine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test class by checking if test should run."""
        if not should_run_test_for_gfa("gfa_operations", GFA_FILE):
            raise unittest.SkipTest(f"No '# test: gfa_operations' comment found in {GFA_FILE}")

        cls.graph = pygfa.gfa.GFA()
        cls.graph.from_gfa(GFA_FILE)

    def test_nodes_connected_components(self):
        nodes = set(self.graph.nodes())
        self.assertTrue({"s1", "fragment5", "s2", "s3", "s4", "s5"} in pygfa.nodes_connected_components(self.graph))
        nodes.remove("s1")
        nodes.remove("s2")
        nodes.remove("s3")
        nodes.remove("s4")
        nodes.remove("s5")
        nodes.remove("fragment5")
        self.assertTrue({"s6", "s7"} in pygfa.nodes_connected_components(self.graph))
        nodes.remove("s6")
        nodes.remove("s7")
        self.assertTrue({"s8"} in pygfa.nodes_connected_components(self.graph))
        nodes.remove("s8")
        self.assertTrue(nodes == set())

    def test_nodes_connected_component(self):
        self.assertTrue(
            {"s1", "s2", "s3", "s4", "s5", "fragment5"} == pygfa.nodes_connected_component(self.graph, "s4")
        )
        with self.assertRaises(pygfa.gfa.GFAError):
            pygfa.nodes_connected_component(self.graph, "42")


if __name__ == "__main__":
    unittest.main()
