import copy
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
#                                                     ~
#                                                      ~ [fragment5]
# [s6_s6] --- [s7_s7]                [s8_s8_s8]
#

GFA_FILE = os.path.join(os.path.dirname(__file__), "data", "test_dovetail_operations.gfa")


class TestLine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test class by checking if test should run."""
        if not should_run_test_for_gfa("dovetail_operations", GFA_FILE):
            raise unittest.SkipTest(f"No '# test: dovetail_operations' comment found in {GFA_FILE}")

        cls.graph = pygfa.gfa.GFA()
        cls.graph.from_gfa(GFA_FILE)

    def test_dovetails_remove_small_components(self):
        copy_ = copy.deepcopy(self.graph)

        pygfa.dovetails_remove_small_components(copy_, 36)
        self.assertTrue({"s1", "s2", "s3"} in pygfa.nodes_connected_components(copy_))
        self.assertTrue({"s4", "s5"} not in pygfa.nodes_connected_components(copy_))

        # BAD BEHAVIOR! It's a side effect of considering only
        # dovetails overlaps while computing the connected components.
        # I tried to erase the normal component once computed
        # the legth, but it made things worse, because:
        #     1 Nodes of other components were erased
        #     2 Once, solved problem 1 (try not to erase node
        #       belonging to normal components that were detected
        #       by dovetails_connected_components), remained a problem.
        #       The nodes belonging to the normal components that werent
        #       recognized during the dovetails components were erased.
        #       (so all the nodes that weren't linked by dovetail edges.
        #
        self.assertTrue({"fragment5"} in pygfa.nodes_connected_components(copy_))

        self.assertTrue({"s6", "s7"} in pygfa.nodes_connected_components(copy_))
        self.assertTrue({"s8"} not in pygfa.nodes_connected_components(copy_))

        copy_ = copy.deepcopy(self.graph)
        pygfa.dovetails_remove_small_components(copy_, 37)
        self.assertTrue({"s1", "s2", "s3"} in pygfa.nodes_connected_components(copy_))
        self.assertTrue({"s4", "s5"} not in pygfa.nodes_connected_components(copy_))
        self.assertTrue({"fragment5"} in pygfa.nodes_connected_components(copy_))

        self.assertTrue({"s6", "s7"} not in pygfa.nodes_connected_components(copy_))
        self.assertTrue({"s8"} not in pygfa.nodes_connected_components(copy_))

        with self.assertRaises(ValueError):
            pygfa.dovetails_remove_small_components(copy_, -1)

    def test_dovetails_remove_dead_ends(self):
        copy_ = copy.deepcopy(self.graph)
        pygfa.dovetails_remove_dead_ends(copy_, 22)

        self.assertTrue("s1" in copy_)
        self.assertTrue("s3" not in copy_)

        self.assertTrue("s5" not in copy_)
        self.assertTrue("s4" not in copy_)

        # fragment5 is considered as a separate node
        # so, considering only dovetails overlap
        # it's seen as an isolated node.
        self.assertTrue("fragment5" not in copy_)

        # s7 is 24bp, so it hasn't been erased
        self.assertTrue("s7" in copy_)
        self.assertTrue("s6" not in copy_)

        self.assertTrue("s8" not in copy_)

        # test safe remove
        copy_ = copy.deepcopy(self.graph)
        pygfa.dovetails_remove_dead_ends(copy_, 22, safe_remove=True)

        self.assertTrue("s1" in copy_)
        self.assertTrue("s3" not in copy_)

        self.assertTrue("s5" not in copy_)
        self.assertTrue("s4" not in copy_)

        # it's not possible to retriev fragment5
        # length, so keep it
        self.assertTrue("fragment5" in copy_)

        # s7 is 24bp, so it hasn't been erased
        self.assertTrue("s7" in copy_)
        self.assertTrue("s6" not in copy_)

        self.assertTrue("s8" not in copy_)

        with self.assertRaises(ValueError):
            pygfa.dovetails_remove_dead_ends(copy_, -1)


if __name__ == "__main__":
    unittest.main()
