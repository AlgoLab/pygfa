#!/usr/bin/env python3
"""
Isolate benchmark functionality in test directory to make it self-contained.
"""

import os


def copy_benchmark_functions():
    """Copy benchmark filter functions to test directory."""

    source_file = "../tools/benchmark_filter.py"
    target_file = "benchmark_filter.py"

    if not os.path.exists(target_file):
        print(f"Creating {target_file}...")
        with open(target_file, "w") as f:
            with open(source_file, "r") as src:
                for line in src:
                    f.write(line)
        print(f"✓ Created {target_file}")
    else:
        print(f"✓ {target_file} already exists")


def update_snakefile():
    """Update Snakefile to use benchmark functions from test directory."""

    snakefile_path = "../workflow/Snakefile"

    # Read current Snakefile
    with open(snakefile_path, "r") as f:
        content = f.read()

    # Replace old import with new import from test directory
    old_import = "from pygfa.tools.benchmark_filter import filter_gfa_files, extract_header_comments"
    new_import = "from test.benchmark_filter import filter_gfa_files, extract_header_comments"

    if old_import in content:
        content = content.replace(old_import, new_import)
        print(f"✓ Updated {snakefile_path}")

        with open(snakefile_path, "w") as f:
            f.write(content)
        print("✓ Snakefile now uses isolated benchmark functions")
    else:
        print(f"✓ {snakefile_path} already uses test directory benchmark functions")


def main():
    print("Isolating benchmark functionality...")
    copy_benchmark_functions()
    update_snakefile()
    print("✅ Benchmark functionality isolated in test directory")
    print("\nTo test benchmark system:")
    print("  1. Test isolation: pixi run python -m pytest test/test_bgfa.py -v")
    print("  2. Test Snakefile: pixi run snakemake -s workflow/Snakefile -n")


if __name__ == "__main__":
    main()
