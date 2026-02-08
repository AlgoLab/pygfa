# Import individual modules to avoid circular import
from pygfa.graph_element.parser.containment import Containment
from pygfa.graph_element.parser.header import Header
from pygfa.graph_element.parser.link import Link
from pygfa.graph_element.parser.path import Path
from pygfa.graph_element.parser.segment import SegmentV1

# Remove removed modules imports
# from pygfa.graph_element.parser.fragment import Fragment  # GFA2 - REMOVED
# from pygfa.graph_element.parser.edge import Edge  # GFA2 - REMOVED
# from pygfa.graph_element.parser.gap import Gap  # GFA2 - REMOVED
# from pygfa.graph_element.parser.group import Group  # GFA2 - REMOVED

__all__ = [
    "containment",
    "header",
    "link",
    "path",
    "segment",
]
