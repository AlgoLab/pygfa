"""
Edge module for GFA graph elements.
"""

from pygfa.graph_element.parser import line, field_validator as fv
from pygfa.graph_element.parser.edge import Edge as EdgeLine


class InvalidEdgeError(Exception):
    pass


def is_edge(obj):
    """Return True if the given object is an Edge."""
    return isinstance(obj, Edge)


class Edge:
    """Represents an edge in a GFA graph.
    
    An edge connects two nodes (segments) with orientations and may have
    an overlap specified as a CIGAR string.
    """

    def __init__(self, eid, from_node, from_orn, to_node, to_orn,
                 from_positions, to_positions, alignment, distance, variance,
                 opt_fields={}, is_dovetail=False):
        """Initialize an Edge object.
        
        :param eid: Edge identifier (can be None for virtual edges)
        :param from_node: Source node identifier
        :param from_orn: Source orientation ('+' or '-')
        :param to_node: Destination node identifier
        :param to_orn: Destination orientation ('+' or '-')
        :param from_positions: Tuple of (start, end) positions on source node
        :param to_positions: Tuple of (start, end) positions on destination node
        :param alignment: CIGAR string describing the overlap
        :param distance: Distance between nodes
        :param variance: Variance of the distance
        :param opt_fields: Dictionary of optional fields
        :param is_dovetail: Whether this is a dovetail overlap
        """
        self.eid = eid
        self.from_node = from_node
        self.from_orn = from_orn
        self.to_node = to_node
        self.to_orn = to_orn
        self.from_positions = from_positions
        self.to_positions = to_positions
        self.alignment = alignment
        self.distance = distance
        self.variance = variance
        self.opt_fields = opt_fields
        self.is_dovetail = is_dovetail
        
        # Add segment end attributes (used for dovetail operations)
        self.from_segment_end = None
        self.to_segment_end = None
        
        # Validate required fields
        if from_node is None:
            raise InvalidEdgeError("from_node cannot be None")
        if to_node is None:
            raise InvalidEdgeError("to_node cannot be None")
        if from_orn not in ['+', '-']:
            raise InvalidEdgeError(f"Invalid from_orn: {from_orn}")
        if to_orn not in ['+', '-']:
            raise InvalidEdgeError(f"Invalid to_orn: {to_orn}")
        
        # Validate positions
        if not isinstance(from_positions, tuple) or len(from_positions) != 2:
            raise InvalidEdgeError(f"Invalid from_positions tuple: given: {str(from_positions)}")
        if not isinstance(to_positions, tuple) or len(to_positions) != 2:
            raise InvalidEdgeError(f"Invalid to_positions tuple: given: {str(to_positions)}")

    @classmethod
    def from_line(cls, edge_line):
        """Create an Edge from an EdgeLine object.
        
        :param edge_line: EdgeLine object
        :return: Edge object
        """
        if not isinstance(edge_line, EdgeLine):
            raise InvalidEdgeError("Expected EdgeLine object")
        
        # Extract fields from the EdgeLine
        fields = edge_line.fields
        
        eid = fields.get('eid', None)
        from_node = fields.get('from_node')
        from_orn = fields.get('from_orn')
        to_node = fields.get('to_node')
        to_orn = fields.get('to_orn')
        
        # For Link lines, positions are None
        from_positions = (None, None)
        to_positions = (None, None)
        
        alignment = fields.get('alignment')
        distance = fields.get('distance', None)
        variance = fields.get('variance', None)
        
        # Extract optional fields
        opt_fields = {}
        for key, value in fields.items():
            if key not in ['eid', 'from_node', 'from_orn', 'to_node', 'to_orn', 
                          'from_positions', 'to_positions', 'alignment', 
                          'distance', 'variance', 'is_dovetail']:
                opt_fields[key] = value
        
        is_dovetail = fields.get('is_dovetail', False)
        
        return cls(eid, from_node, from_orn, to_node, to_orn,
                   from_positions, to_positions, alignment, distance, variance,
                   opt_fields, is_dovetail)

    def __eq__(self, other):
        """Check if two edges are equal (ignoring IDs)."""
        if not isinstance(other, Edge):
            return False
        
        return (self.from_node == other.from_node and
                self.from_orn == other.from_orn and
                self.to_node == other.to_node and
                self.to_orn == other.to_orn and
                self.alignment == other.alignment and
                self.distance == other.distance and
                self.variance == other.variance and
                self.is_dovetail == other.is_dovetail and
                self.opt_fields == other.opt_fields)

    def __repr__(self):
        return f"Edge({self.from_node}{self.from_orn}->{self.to_node}{self.to_orn})"
