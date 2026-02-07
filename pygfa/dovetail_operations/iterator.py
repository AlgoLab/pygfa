"""
Standalone dovetail operations functions.

This module provides dovetail-specific graph operations
without requiring the full iterator infrastructure.
"""

from __future__ import annotations


def dovetails_articulation_points(gfa_):
    """Redefinition of articulation point for dovetails connected components."""
    articulation_points = []
    for node_ in gfa_.nodes():
        right_deg = gfa_.right_degree(node_)
        left_deg = gfa_.left_degree(node_)
        # Node is articulation point if removing it would disconnect graph
        if (right_deg > 1 and left_deg > 1) or \
           (right_deg == 1 and left_deg > 1) or \
           (right_deg > 1 and left_deg == 1):
            articulation_points.append(node_)
    return articulation_points


def dovetails_remove_small_components(gfa_, min_length):
    """Remove all connected components where sequences length is less than min_length."""
    if min_length < 0:
        raise ValueError("min_length must be >= 0")
    
    # Get all connected components
    components = list(gfa_.connected_components())
    
    for comp in components:
        # Calculate total sequence length
        length = 0
        for node_id in comp:
            node_ = gfa_.nodes(identifier=node_id)
            if node_ and node_.get('slen'):
                length += node_['slen']
        
        if length < min_length:
            # Remove all nodes in this component
            for node_id in comp:
                gfa_.remove_node(node_id)


def dovetails_remove_dead_ends(gfa_, min_length, safe_remove=False):
    """Remove nodes with degree (0,0), (0,1), or (1,0) and length < min_length."""
    if min_length < 0:
        raise ValueError("min_length must be >= 0")
    
    articulation_points = dovetails_articulation_points(gfa_)
    to_remove = []
    
    for node_id in gfa_.nodes():
        right_deg = gfa_.right_degree(node_id)
        left_deg = gfa_.left_degree(node_id)
        
        if ((right_deg, left_deg) in [(0,0), (0,1), (1,0)]) and \
           node_id not in articulation_points):
            node_ = gfa_.nodes(identifier=node_id)
            length = node_.get('slen', 0) if node_ else 0
            
            if not safe_remove or (length is not None and length >= min_length):
                to_remove.append(node_id)
    
    for node_id in to_remove:
        gfa_.remove_node(node_id)