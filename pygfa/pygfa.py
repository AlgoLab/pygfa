import sys
import re
from parser.lines import header, segment, link, containment, path, group, gap, edge, fragment
import gfa
import networkx as nx
import matplotlib.pyplot as plt
from graph_element import node, edge as ge

def from_file (filepath):
    try:
        pygfa = gfa.GFA ()
        with open (filepath) as file:
            for line in file:
                line = line.strip ()
                if line[0] == 'S':
                    if segment.is_segmentv1 (line):
                        pygfa.add (node.Node.from_line (segment.SegmentV1.from_string (line)))
                    else:
                        pygfa.add (node.Node.from_line (segment.SegmentV2.from_string (line)))
                elif line[0] == 'L':
                    pygfa.add (ge.Edge.from_line (link.Link.from_string (line)))
                elif line[0] == 'C':
                    pygfa.add (ge.Edge.from_line (containment.Containment.from_string (line)))
                elif line[0] == 'E':
                    pygfa.add (ge.Edge.from_line (edge.Edge.from_string (line)))
                elif line[0] == 'G':
                    pygfa.add (ge.Edge.from_line (gap.Gap.from_string (line)))
                elif line[0] == 'F':
                    pygfa.add (ge.Edge.from_line (fragment.Fragment.from_string (line)))
                    

        return pygfa
    except IOError as ioe:
        print (ioe)

def make_graph (self):
    """Make a graph where each segment is a node, and each edge is a link."""
    
        
if __name__ == '__main__':

    
    
    try:
        tmp_pygfa = from_file (sys.argv[1])
        print (tmp_pygfa.pprint ())

        edge_labels = dict ( [ \
                                   ( (node1, node2), key )\
                                   for node1, node2, key in tmp_pygfa.edges(keys=True) \
                                   ])

        layout = nx.spring_layout (tmp_pygfa._graph)
        nx.draw (tmp_pygfa, layout, with_labels = True)
        nx.draw_networkx_edge_labels (tmp_pygfa, layout, edge_labels = edge_labels)
        plt.show ()

    except Exception as e:
        raise (e)
