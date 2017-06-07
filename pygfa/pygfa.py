import sys
import re
from parser.lines import header, segment, link, containment, path
import networkx as nx
import matplotlib.pyplot as plt

class PyGFA:

    def __init__ (self):
        self.headers = []
        self.links = []
        self.segments = []
        self.paths = []
        self.containments = []

    @staticmethod
    def from_file (filepath):
        try:
            pygfa = PyGFA ()
            with open (filepath) as file:
                for line in file:
                    line = line.strip ()
                    if line[0] == 'H':
                        pygfa.headers.append (header.Header.from_string (line))
                    elif line[0] == 'P':
                        pygfa.paths.append (path.Path.from_string (line))
                    elif line[0] == 'S':
                        pygfa.segments.append (segment.SegmentV1.from_string (line))
                    elif line[0] == 'L':
                        pygfa.links.append (link.Link.from_string (line))
                    elif line[0] == 'C':
                        pygfa.containments.append (containment.Containment.from_string (line))

            return pygfa
        except IOError as ioe:
            print (ioe)

    def make_graph (self):
        """Make a graph where each segment is a node, and each edge is a link."""
        graph = nx.Graph ()
        for item in self.segments:
            graph.add_node (item.fields['name'].value, object = item)

        for item in self.links:
            from_node = item.fields['from'].value
            to_node = item.fields['to'].value
            graph.add_edge (from_node, to_node, overlap = item.fields['overlap'].value)

       

        return graph
        
if __name__ == '__main__':

    try:
        tmp_pygfa = PyGFA.from_file (sys.argv[1])

        tmp_graph = tmp_pygfa.make_graph ()

        # retrieves the overlap inside the graph edges to visualize them as weight
        edge_labels = dict ( [ \
                                   ( (node1, node2), data['overlap']) \
                                   for node1, node2, data in tmp_graph.edges(data=True) \
                                   ])

        layout = nx.spring_layout (tmp_graph)
        nx.draw (tmp_graph, layout, with_labels = True)
        nx.draw_networkx_edge_labels (tmp_graph, layout, edge_labels = edge_labels)
        plt.show ()

    except Exception as e:
        print (e)
