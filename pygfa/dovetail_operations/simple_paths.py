import networkx as nx

from pygfa.algorithms.simple_paths import all_simple_paths

def dovetails_all_simple_paths(gfa_, source, target, edges, cutoff=None):
    return all_simple_paths(\
                            gfa_, \
                            source, \
                            target, \
                            gfa_.dovetails_iter, \
                            edges=edges, \
                            cutoff=cutoff, \
                            keys=True) # argument for gfa_dovetails_iter
