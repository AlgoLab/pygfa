"""A module rewritten using the simple_paths networkx module
To provide a convenient and reusable way to specificy
A custom iterator to use in the algorithm (using only
algorithms for multigraphs)

The same documentation for networkx is valid using this algorithms."""

import networkx as nx
from typing import Callable, Iterable, Iterator, List, Optional, Tuple, Union

__all__ = ["all_simple_paths"]


def all_simple_paths(gfa_, source: str, target: str, selector: Callable[..., Iterable[Tuple[str, str]]], edges: bool = False, keys: bool = True, cutoff: Optional[int] = None) -> Union[Iterator[List[str]], Iterator[List[Tuple[str, Optional[str]]]]]:
    """Compute the all_simple_path algorithm as described in
    networkx, but return the edges keys if asked and use the
    given selector to obtain the nodes to consider.

    :param selector: A function or a method used to select the nodes
        to consider, the selector MUST give back two values at least and
        three values considering the keys. So the selector must be a
        similar networkx edges selectors (at least in behavior).
    :param edges: If True return the edges key that connect each pair of nodes
        in the simple path, each data is given in the format
        `(node_to, edge_that_connect_previous_to_node_to)`, so
        source node and target node will be in the form `(node, None)`.
    :param args: Optional arguments to supply to selector.
    """
    if source not in gfa_:
        raise nx.NetworkXError(f"source node {source} not in graph")
    if target not in gfa_:
        raise nx.NetworkXError(f"target node {target} not in graph")
    if cutoff is None:
        cutoff = len(gfa_.nodes()) - 1
    if edges is False:
        return _all_simple_paths_multigraph(gfa_, source, target, selector, cutoff=cutoff)
    else:
        return _all_simple_paths_edges_multigraph(
            gfa_, source, target, selector, keys=keys, cutoff=cutoff
        )


def _all_simple_paths_multigraph(_gfa, source: str, target: str, selector: Callable[..., Iterable[Tuple[str, str]]], cutoff: Optional[int] = None) -> Iterator[List[str]]:
    if cutoff < 1:
        return
    visited = [source]
    stack = [(v for u, v in selector(source))]
    while stack:
        children = stack[-1]
        child = next(children, None)
        if child is None:
            stack.pop()
            visited.pop()
        elif len(visited) < cutoff:
            if child == target:
                yield [*visited, target]
            elif child not in visited:
                visited.append(child)
                stack.append((v for u, v in selector(child)))
        else:
            count = ([child] + list(children)).count(target)
            for _i in range(count):
                yield [*visited, target]
            stack.pop()
            visited.pop()


def _all_simple_paths_edges_multigraph(_gfa, source: str, target: str, selector: Callable[..., Iterable[Union[Tuple[str, str], Tuple[str, str, str]]]], keys: bool = False, cutoff: Optional[int] = None) -> Iterator[List[Tuple[str, Optional[str]]]]:
    """Return all simple paths from source to target with
    all the edges id that connect each pair of nodes.
    """
    if cutoff < 1:
        return
    path = []
    visited = [source]
    stack = (
        [((u, v, k) for u, v, k in selector(source, keys=True))]
        if keys
        else [((u, v) for u, v in selector(source, keys=True))]
    )
    while stack:
        children = stack[-1]
        child = next(children, None)

        if child is None:
            stack.pop()
            visited.pop()

            if path:
                path.pop()
        elif len(visited) < cutoff:
            if child[1] == target:
                yield [*path, child]
            elif child[1] not in visited:
                visited.append(child[1])
                path.append(child)
                add_to_stack = (
                    ((u, v, k) for u, v, k in selector(child[1], keys=True))
                    if keys
                    else ((u, v) for u, v in selector(child[1], keys=True))
                )
                stack.append(add_to_stack)
        else:
            count = ([child[1]] + [child_[1] for child_ in children]).count(target)
            for _i in range(count):
                yield [*path, child]
            stack.pop()
            visited.pop()
            path.pop()
            if path:
                path.pop()
        elif len(visited) < cutoff:
            if child[1] == target:
                yield [*path, child]
            elif child[1] not in visited:
                visited.append(child[1])
                path.append(child)
                add_to_stack = (
                    ((u, v, k) for u, v, k in selector(child[1], keys=True))
                    if keys
                    else ((u, v) for u, v in selector(child[1], keys=True))
                )
                stack.append(add_to_stack)
        else:
            count = ([child[1]] + [child_[1] for child_ in children]).count(target)
            for _i in range(count):
                yield [*path, child]
            stack.pop()
            visited.pop()
            path.pop()
            if path:
                path.pop()
