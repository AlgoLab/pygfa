"""A module rewritten using the simple_paths networkx module
to provide a convenient and reusable way to specificy
a custom iterator to use in the algorithm (using only
algorithms for multigraphs)

The same documentation for networkx is valid using this algorithms."""

#    Copyright (C) 2012 by
#    Sergio Nery Simoes <sergionery@gmail.com>
#    All rights reserved.
#    BSD license.
import networkx as nx

def all_simple_paths(gfa_, source, target, selector, edges=False, cutoff=None, **args):
    """Compute the all_simple_path algorithm as described in 
    networkx, but return the edges keys if asked and use the
    given selector to obtain the nodes to consider.

    :param selector: A function or a method used to select the nodes
        to consider.
    :param edges: If True return the edges key that connect each pair of nodes
        in the simple path, each data is given in the format
        `(node_to, edge_that_connect_previous_to_node_to)`, so
        source node and target node will be in the form `(node, None)`.
    :param args: Optional arguments to supply to selector.
    """
    if source not in gfa_:
        raise nx.NetworkXError('source node %s not in graph'%source)
    if target not in gfa_:
        raise nx.NetworkXError('target node %s not in graph'%target)
    if cutoff is None:
        cutoff = len(gfa_.nodes())-1
    if edges is False:
        return _all_simple_paths_multigraph(gfa_, source, target, selector, cutoff=cutoff, **args)
    else:
        return _all_simple_paths_edges_multigraph(gfa_, source, target, selector, cutoff=cutoff, **args)


def _all_simple_paths_multigraph(gfa_, source, target, selector, cutoff=None, **args):
    if cutoff < 1:
        return
    visited = [source]
    # stack = [(v for u,v in gfa_.edges(source))]
    stack = [(v for u,v in selector(source, **args))]
    while stack:
        children = stack[-1]
        child = next(children, None)
        if child is None:
            stack.pop()
            visited.pop()
        elif len(visited) < cutoff:
            if child == target:
                yield visited + [target]
            elif child not in visited:
                visited.append(child)
                # stack.append((v for u,v in gfa_.edges(child)))
                stack.append((v for u,v in selector(child, **args)))
        else: #len(visited) == cutoff:
            count = ([child]+list(children)).count(target)
            for i in range(count):
                yield visited + [target]
            stack.pop()
            visited.pop()

def _all_simple_paths_edges_multigraph(gfa_, source, target, selector, cutoff=None, **args):
    """Return all simple paths from source to target with
    all the edges id that connect each pair of nodes.
    """
    # the algorithm has been extended to work with
    # a list of tuples, in the form (node, edge_from_previous_to_this_node)
    # so in order to avoid the extraction of the same node
    # with different edges (generating duplication of paths)
    # the nodes are always extracted in the main
    # comparations (i.e. child not in visited has become:
    #
    #     child[0] not in [all the nodes visited]
    #
    # and so on.
    # This sections are, for sake of completeness, indicated
    # by side comments in the code (look for the "here").
    if cutoff < 1:
        return
    visited = [(source, None)]
    # stack = [(v for u,v in gfa_.edges(source))]
    stack = [((v,k) for u,v,k in selector(source, **args))]
    while stack:
        children = stack[-1]
        child = next(children, None)
        if child is None:
            stack.pop()
            visited.pop()
        elif len(visited) < cutoff:
            if child[0] == target:    # here
                yield visited + [(target, None)]
            elif child[0] not in [v[0] for v in visited]:    # here
                visited.append(child)
                # stack.append((v for u,v in gfa_.edges(child)))
                stack.append(((v, k) for u,v,k in selector(child, **args)))
        else: #len(visited) == cutoff:
            count = ([child[0]]+list(child[0] for child in children)).count(target)    # here
            for i in range(count):
                yield visited + [(target, None)]
            stack.pop()
            visited.pop()
