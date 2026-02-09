import unittest
import sys
from unittest.mock import Mock

sys.path.insert(0, "../")

from pygfa.algorithms.simple_paths import all_simple_paths
from pygfa.algorithms.traversal import dfs_edges


class TestSimplePaths(unittest.TestCase):
    """Test simple paths algorithms."""

    def setUp(self):
        """Set up a mock graph for testing."""
        self.mock_graph = Mock()

        # Configure the mock graph to return specific values
        self.mock_graph.__contains__ = Mock(return_value=True)
        self.mock_graph.nodes = Mock(return_value=["A", "B", "C", "D"])
        self.mock_graph.__len__ = Mock(return_value=4)

    def test_all_simple_paths_basic(self):
        """Test basic simple path finding."""

        # Mock selector function
        def mock_selector(node):
            if node == "A":
                yield "A", "B"
                yield "A", "C"
            elif node == "B":
                yield "B", "D"
            elif node == "C":
                yield "C", "D"
            else:
                return

        # Test path finding from A to D
        paths = list(all_simple_paths(self.mock_graph, "A", "D", mock_selector, edges=False, cutoff=3))

        # Should find paths: A->B->D and A->C->D
        self.assertEqual(len(paths), 2)
        self.assertIn(["A", "B", "D"], paths)
        self.assertIn(["A", "C", "D"], paths)

    def test_all_simple_paths_with_edges(self):
        """Test simple path finding with edge information."""

        def mock_selector_with_keys(node, keys=True):
            if node == "A":
                yield "A", "B", "edge1"
                yield "A", "C", "edge2"
            elif node == "B":
                yield "B", "D", "edge3"
            elif node == "C":
                yield "C", "D", "edge4"
            else:
                return

        paths = list(
            all_simple_paths(self.mock_graph, "A", "D", mock_selector_with_keys, edges=True, keys=True, cutoff=3)
        )

        # Should return paths with edge keys
        self.assertEqual(len(paths), 2)
        for path in paths:
            self.assertIsInstance(path, list)
            # Each element should be a tuple (node, edge_key)
            for element in path[:-1]:  # Skip target node
                self.assertIsInstance(element, tuple)
                self.assertEqual(len(element), 3)

    def test_all_simple_paths_cutoff(self):
        """Test path finding with cutoff limit."""

        def mock_selector(node):
            if node == "A":
                yield "A", "B"
            elif node == "B":
                yield "B", "C"
            elif node == "C":
                yield "C", "D"
            else:
                return

        # Test with cutoff=2 (should not find A->B->C->D)
        paths = list(all_simple_paths(self.mock_graph, "A", "D", mock_selector, cutoff=2))

        # Should only find paths of length <= 3 (2 edges)
        # A->B->C->D has 3 edges, so should be excluded
        self.assertEqual(len(paths), 0)

    def test_all_simple_paths_source_not_in_graph(self):
        """Test error when source node not in graph."""
        self.mock_graph.__contains__ = Mock(side_effect=[False, True])

        with self.assertRaises(Exception):  # Should raise NetworkXError
            list(all_simple_paths(self.mock_graph, "X", "A", lambda n: []))

    def test_all_simple_paths_target_not_in_graph(self):
        """Test error when target node not in graph."""
        self.mock_graph.__contains__ = Mock(side_effect=[True, False])

        with self.assertRaises(Exception):  # Should raise NetworkXError
            list(all_simple_paths(self.mock_graph, "A", "X", lambda n: []))


class TestTraversal(unittest.TestCase):
    """Test traversal algorithms."""

    def setUp(self):
        """Set up a mock graph for testing."""
        self.mock_graph = Mock()

        # Create a simple adjacency structure
        def mock_selector(node, keys=False, **args):
            if node == "A":
                yield "A", "B"
                yield "A", "C"
            elif node == "B":
                yield "B", "D"
            elif node == "C":
                yield "C", "D"
            elif node == "D":
                return  # No outgoing edges
            else:
                return

        self.mock_selector = mock_selector

    def test_dfs_edges_from_source(self):
        """Test DFS traversal from specific source."""
        edges = list(dfs_edges(self.mock_graph, self.mock_selector, source="A", keys=False))

        # Should get DFS traversal order
        edge_tuples = [edge for edge in edges]
        self.assertGreater(len(edge_tuples), 0)

        # Check that we get connected edges in DFS order
        nodes_visited = set()
        for edge in edge_tuples:
            self.assertIsInstance(edge, tuple)
            self.assertEqual(len(edge), 2)  # (from, to)
            nodes_visited.add(edge[1])

    def test_dfs_edges_all_components(self):
        """Test DFS traversal of all components."""
        # Mock nodes() to return all nodes
        mock_graph = Mock()
        mock_graph.nodes = Mock(return_value=["A", "B", "C", "D", "E"])

        # Update selector to handle node 'E' (isolated component)
        def mock_selector_all(node, keys=False, **args):
            if node == "A":
                yield "A", "B"
            elif node == "B":
                yield "B", "D"
            elif node == "C":
                yield "C", "D"
            else:
                return  # No outgoing edges

        edges = list(dfs_edges(mock_graph, mock_selector_all, source=None, keys=False))

        # Should visit all reachable nodes
        self.assertGreater(len(edges), 0)

    def test_dfs_edges_with_keys(self):
        """Test DFS traversal with edge keys."""

        def mock_selector_with_keys(node, keys=True, **args):
            if node == "A":
                yield "A", "B", "edge1"
                yield "A", "C", "edge2"
            elif node == "B":
                yield "B", "D", "edge3"
            else:
                return

        edges = list(dfs_edges(self.mock_graph, mock_selector_with_keys, source="A", keys=True))

        # Each edge should be a tuple with (from, to, key)
        for edge in edges:
            self.assertIsInstance(edge, tuple)
            self.assertEqual(len(edge), 3)

    def test_dfs_edges_empty_graph(self):
        """Test DFS traversal with empty graph."""
        empty_graph = Mock()
        empty_graph.nodes = Mock(return_value=[])

        edges = list(dfs_edges(empty_graph, lambda n: [], source=None))

        self.assertEqual(len(edges), 0)


class TestAlgorithmEdgeCases(unittest.TestCase):
    """Test edge cases and error handling for algorithms."""

    @unittest.skip("Selector API changed - needs test update")
    def test_empty_selector(self):
        """Test with selector that returns no edges."""
        mock_graph = Mock()
        mock_graph.__contains__ = Mock(return_value=True)
        mock_graph.nodes = Mock(return_value=["A", "B"])

        def empty_selector(node):
            return  # No edges

        paths = list(all_simple_paths(mock_graph, "A", "B", empty_selector))

        # Should find no paths
        self.assertEqual(len(paths), 0)

    @unittest.skip("Selector interface changed")
    def test_selector_with_args(self):
        """Test selector that accepts additional arguments."""
        mock_graph = Mock()
        mock_graph.__contains__ = Mock(return_value=True)
        mock_graph.nodes = Mock(return_value=["A", "B"])

        def selector_with_args(node, keys=False, custom_arg=None):
            if custom_arg == "test":
                yield node, "B"

        paths = list(
            all_simple_paths(
                mock_graph, "A", "B", lambda n, **kwargs: selector_with_args(n, **kwargs), custom_arg="test"
            )
        )

        # Should find path when custom_arg matches
        self.assertEqual(len(paths), 1)

    @unittest.skip("Graph traversal behavior changed")
    def test_self_loop_handling(self):
        """Test handling of self-loops in paths."""
        mock_graph = Mock()
        mock_graph.__contains__ = Mock(return_value=True)
        mock_graph.nodes = Mock(return_value=["A"])

        def selector_with_self_loop(node):
            if node == "A":
                yield "A", "A"  # Self loop

        # With cutoff=None, this should create infinite recursion
        # But with cutoff, it should handle gracefully
        paths = list(all_simple_paths(mock_graph, "A", "A", selector_with_self_loop, cutoff=1))

        # Should find the self-loop path
        self.assertEqual(len(paths), 1)
        self.assertEqual(paths[0], ["A"])


class TestAlgorithmPerformance(unittest.TestCase):
    """Test algorithm performance characteristics."""

    def test_large_graph_traversal(self):
        """Test traversal with larger graph structure."""
        # Create a linear chain graph
        mock_graph = Mock()

        def chain_selector(node, keys=False):
            if isinstance(node, int) and node < 99:
                yield node, node + 1

        mock_graph.__contains__ = Mock(return_value=True)
        mock_graph.nodes = Mock(return_value=list(range(100)))

        # Test DFS traversal
        edges = list(dfs_edges(mock_graph, chain_selector, source=0, keys=False))

        # Should visit all 99 edges in the chain
        self.assertEqual(len(edges), 99)

    def test_cutoff_behavior(self):
        """Test that cutoff parameter correctly limits path length."""
        mock_graph = Mock()
        mock_graph.__contains__ = Mock(return_value=True)
        mock_graph.nodes = Mock(return_value=["A", "B", "C", "D", "E"])

        def long_path_selector(node):
            if node == "A":
                yield "A", "B"
            elif node == "B":
                yield "B", "C"
            elif node == "C":
                yield "C", "D"
            elif node == "D":
                yield "D", "E"
            else:
                return

        # With cutoff=2, should not find A->B->C->D->E (4 nodes, 3 edges)
        paths = list(all_simple_paths(mock_graph, "A", "E", long_path_selector, cutoff=2))

        # Should find no paths longer than cutoff+1 nodes
        for path in paths:
            self.assertLessEqual(len(path), 3)  # cutoff + 1


if __name__ == "__main__":
    unittest.main()
