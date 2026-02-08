#!/usr/bin/env python3
"""
Minimal fix for critical import issues in pygfa test suite.
Focuses on fixing the parser imports that are blocking all tests.
"""

import sys
import os

def fix_critical_imports():
    """Fix the critical import issues in parser __init__.py."""
    
    init_file = "/home/gianluca/Devel/pangenome/pygfa/pygfa/graph_element/parser/__init__.py"
    
    print(f"Fixing {init_file}...")
    
    with open(init_file, 'r') as f:
        content = f.read()
    
def fix_critical_imports():
    """Fix the critical import issues in parser __init__.py."""
    
    init_file = "/home/gianluca/Devel/pangenome/pygfa/pygfa/graph_element/parser/__init__.py"
    
    print(f"Fixing {init_file}...")
    
    with open(init_file, 'r') as f:
        content = f.read()
    
    # Simple, direct fix - replace problematic imports
    old_imports = [
        "from pygfa.graph_element.parser.segment import Segment, SegmentV2",
        "from pygfa.graph_element.parser.fragment import Fragment",
        "from pygfa.graph_element.parser.edge import Edge",
        "from pygfa.graph_element.parser.gap import Gap", 
        "from pygfa.graph_element.parser.group import Group"
    ]
    
    new_imports = [
        "from pygfa.graph_element.parser.segment import SegmentV1",
        "from pygfa.graph_element.parser.containment import Containment",
        "from pygfa.graph_element.parser.header import Header",
        "from pygfa.graph_element.parser.link import Link",
        "from pygfa.graph_element.parser.path import Path"
    ]
    
    fixed_content = content
    for old_import in old_imports:
        if old_import in content:
            fixed_content = fixed_content.replace(old_import, "")
    
    # Remove removed modules imports
    lines = content.split('\n')
    fixed_lines = []
    for line in lines:
        if not any(removed in line for removed in ["fragment", "edge", "gap", "group"]):
            fixed_lines.append(line)
    
    if '\n'.join(fixed_lines) != content:
        with open(init_file, 'w') as f:
            f.write('\n'.join(fixed_lines))
        print("✅ Fixed parser imports")
    else:
        print("⚠️ Parser imports already fixed")
    
    return fixed_content != content
"""
    
    if old_content != fixed_content:
        with open(init_file, 'w') as f:
            f.write(fixed_content)
        print("✅ Fixed parser imports")
    else:
        print("⚠️ Parser imports already fixed")
    
    return old_content != fixed_content

def fix_sample_benchmark_files():
    """Fix sample GFA files to use only GFA1 format."""
    
    data_dir = "/home/gianluca/Devel/pangenome/pygfa/data"
    sample_files = [
        "sample1_gfa2.gfa",
        "sample2_gfa2.gfa"
        "sample3_gfa2.gfa"
    ]
    
    for filename in sample_files:
        filepath = os.path.join(data_dir, filename)
        if os.path.exists(filepath):
            print(f"Would update {filename} to use GFA1 format - removing if exists")
            # os.remove(filepath)  # Uncomment to actually remove
    
    print("✅ Sample GFA file references checked")

def main():
    print("🔧 Fixing critical pygfa test issues...")
    
    # Fix 1: Critical parser imports
    parser_fixed = fix_critical_imports()
    
    # Fix 2: Check sample files (optional)
    fix_sample_benchmark_files()
    
    if parser_fixed:
        print("✅ Critical import issues fixed")
        print("\n🧪 To test the fixes:")
        print("  1. Parser imports: pixi run python -m pytest test/test_graph_element.py -v")
        print("  2. Benchmark system: pixi run python -c \"import sys; sys.path.insert(0, '.'); from test.benchmark_filter import filter_gfa_files; print('Found', len(filter_gfa_files('data', None)), 'benchmark files')\"")
    else:
        print("⚠️ No changes needed")

if __name__ == "__main__":
    main()