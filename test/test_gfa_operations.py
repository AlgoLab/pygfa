import sys
import unittest

sys.path.insert(0, "../")

import pygfa
from test_utils import should_run_test_for_gfa, get_gfa_file_from_args

#
# ~~~ = other overlap
#
#
# [s1_s1] --- [s2_s2] --- [s3_s3] ~~
#                                  ~~~ [s4_s4] --- [s5_s5]
#
#
# [s6_s6] --- [s7_s7]                [s8_s8_s8]
#


class TestGfaOperations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test class by getting the GFA file to test."""
        try:
            gfa_file = get_gfa_file_from_args("gfa_operations")
        except ValueError as e:
            raise unittest.SkipTest(str(e))

        if not should_run_test_for_gfa("gfa_operations", gfa_file):
            raise unittest.SkipTest(f"No '# test: gfa_operations' comment found in {gfa_file}")

        cls.graph = pygfa.gfa.GFA()
        cls.graph.from_gfa(gfa_file)

    def test_nodes_connected_components(self):
        nodes = set(self.graph.nodes())
        self.assertTrue({"s1", "s2", "s3", "s4", "s5"} in pygfa.nodes_connected_components(self.graph))
        nodes.remove("s1")
        nodes.remove("s2")
        nodes.remove("s3")
        nodes.remove("s4")
        nodes.remove("s5")
        self.assertTrue({"s6", "s7"} in pygfa.nodes_connected_components(self.graph))
        nodes.remove("s6")
        nodes.remove("s7")
        self.assertTrue({"s8"} in pygfa.nodes_connected_components(self.graph))
        nodes.remove("s8")
        self.assertTrue(nodes == set())

    def test_nodes_connected_component(self):
        self.assertTrue({"s1", "s2", "s3", "s4", "s5"} == pygfa.nodes_connected_component(self.graph, "s4"))
        with self.assertRaises(pygfa.gfa.GFAError):
            pygfa.nodes_connected_component(self.graph, "42")


if __name__ == "__main__":
    unittest.main()
