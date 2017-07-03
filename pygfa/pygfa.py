import sys
from parser.lines import header, segment, link, containment, path, group, gap, edge, fragment
import gfa
import networkx as nx
import matplotlib.pyplot as plt
from graph_element import node, edge as ge, subgraph as sg
import argparse

import logging

logging.basicConfig(level=logging.DEBUG)

# -------------------------CLI-ARGUMENT-MANAGEMENT-------------------------------- #
parser = argparse.ArgumentParser (description = "Compute graph structure from GFA file.")
parser.add_argument ('-f', '--file',  metavar='file', type=str, nargs=1, required=True)
parser.add_argument ('-s', '--subgraph',  metavar='subgraph_key', type=str, nargs=1, required=False)
args = parser.parse_args()
# -------------------------------------------------------------------------------- #


if __name__ == '__main__':
    
    try:
        tmp_pygfa = gfa.GFA.from_file (args.file[0])
        print (tmp_pygfa.pprint ())
        node_color = "r"
        
        if (args.subgraph):
            tmp_pygfa = tmp_pygfa.get_subgraph (args.subgraph[0])
            print ("\nSUBGRAPH {0}\n".format (args.subgraph[0]))
            print (tmp_pygfa.pprint ())
            node_color = "b"


        edge_labels = dict ( [ \
                                   ( (node1, node2), key )\
                                   for node1, node2, key in tmp_pygfa.edges(keys=True) \
                                   ])

        layout = nx.spring_layout (tmp_pygfa._graph)
        nx.draw (tmp_pygfa._graph, layout, with_labels = True, node_color=node_color)
        nx.draw_networkx_edge_labels (tmp_pygfa, layout, edge_labels = edge_labels)
        plt.show ()

    except Exception as e:
        raise (e)
