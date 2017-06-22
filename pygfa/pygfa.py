import sys
from parser.lines import header, segment, link, containment, path, group, gap, edge, fragment
import gfa
import networkx as nx
import matplotlib.pyplot as plt
from graph_element import node, edge as ge, subgraph as sg
import argparse

# -------------------------CLI-ARGUMENT-MANAGEMENT-------------------------------- #
parser = argparse.ArgumentParser (description = "Compute graph structure from GFA file.")
parser.add_argument ('-f', '--file',  metavar='file', type=str, nargs=1, required=True)
parser.add_argument ('-s', '--subgraph',  metavar='subgraph_key', type=str, nargs=1, required=False)
args = parser.parse_args()
# -------------------------------------------------------------------------------- #

def from_file (filepath):
    try:
        pygfa = gfa.GFA ()
        with open (filepath) as file:
            for line in file:
                line = line.strip ()
                if line[0] == 'S':
                    if segment.is_segmentv1 (line):
                        pygfa.add_graph_element (node.Node.from_line (segment.SegmentV1.from_string (line)))
                    else:
                        pygfa.add_graph_element (node.Node.from_line (segment.SegmentV2.from_string (line)))
                elif line[0] == 'L':
                    pygfa.add_graph_element (ge.Edge.from_line (link.Link.from_string (line)))
                elif line[0] == 'C':
                    pygfa.add_graph_element (ge.Edge.from_line (containment.Containment.from_string (line)))
                elif line[0] == 'E':
                    pygfa.add_graph_element (ge.Edge.from_line (edge.Edge.from_string (line)))
                elif line[0] == 'G':
                    pygfa.add_graph_element (ge.Edge.from_line (gap.Gap.from_string (line)))
                elif line[0] == 'F':
                    pygfa.add_graph_element (ge.Edge.from_line (fragment.Fragment.from_string (line)))
                elif line[0] == 'P':
                    pygfa.add_graph_element (sg.Subgraph.from_line (path.Path.from_string (line)))
                elif line[0] == 'O':
                    pygfa.add_graph_element (sg.Subgraph.from_line (group.OGroup.from_string (line)))
                elif line[0] == 'U':
                    pygfa.add_graph_element (sg.Subgraph.from_line (group.UGroup.from_string (line)))

        return pygfa
    except IOError as ioe:
        print (ioe)
    
        
if __name__ == '__main__':
    
    try:
        tmp_pygfa = from_file (args.file[0])
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
        nx.draw (tmp_pygfa, layout, with_labels = True, node_color=node_color)
        nx.draw_networkx_edge_labels (tmp_pygfa, layout, edge_labels = edge_labels)
        plt.show ()

    except Exception as e:
        raise (e)
