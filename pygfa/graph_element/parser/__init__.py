# Import individual modules to avoid circular import

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
