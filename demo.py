import sys

import pygfa
import networkx as nx
import matplotlib.pyplot as plt
import argparse

import logging

logging.basicConfig(level=logging.DEBUG)

if __name__ == '__main__':
    
    # -------------------------CLI-ARGUMENT-MANAGEMENT-------------------------------- #
    parser = argparse.ArgumentParser (description="Compute graph structure from GFA file.")
    parser.add_argument('-f', '--file',  metavar='file', type=str, nargs=1, required=True)
    parser.add_argument('-s', '--subgraph',  metavar='subgraph_key', type=str, nargs=1, required=False)
    parser.add_argument('-d', '--display', action='store_true', default=False)
    parser.add_argument('-c', '--convert', metavar=("gfa_version", "output_file"), type=str, nargs=2, \
                             required=False)
    # -------------------------------------------------------------------------------- #

    try:
        args = parser.parse_args()
        
        tmp_pygfa = pygfa.gfa.GFA.from_file (args.file[0])
        node_color = "r"
        
        if args.subgraph:
            tmp_pygfa = tmp_pygfa.get_subgraph (args.subgraph[0])
            node_color = "b"

        if args.display:
            edge_labels = dict ( [ \
                                    ( (node1, node2), key )\
                                    for node1, node2, key in tmp_pygfa.edges(keys=True) \
                                    ])
            layout = nx.spring_layout (tmp_pygfa._graph)
            nx.draw (tmp_pygfa._graph, layout, with_labels = True, node_color=node_color)
            nx.draw_networkx_edge_labels (tmp_pygfa, layout, edge_labels = edge_labels)
            plt.show ()

        if args.convert:
            version = 1
            if args.convert[0] in ("2", "gfa2", "GFA2"):
                version = 2
            elif args.convert[0] in ("1", "gfa1", "GFA1"):
                version = 1
            else:
                raise ValueError("Invalid GFA version given")

            tmp_pygfa.dump(gfa_version=version, out=args.convert[1])
    except SystemExit:
        pass
    except EnvironmentError as env_error:
        print(repr(env_error))

