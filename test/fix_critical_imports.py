import os
import re


def fix_critical_imports():
    """Fix critical import issues in the codebase."""

    fixed_files = []

    # Check if we need to add missing imports to test files
    test_files = [
        "test/test_gfa_graph.py",
    ]

    for test_file in test_files:
        if os.path.exists(test_file):
            with open(test_file, "r") as f:
                content = f.read()

            # Add missing imports if needed
            if "from pygfa.graph_element.parser import" not in content:
                # Find the imports section
                lines = content.split("\n")
                import_lines = []
                other_lines = []
                in_imports = True

                for line in lines:
                    if in_imports and (
                        line.startswith("import ")
                        or line.startswith("from ")
                        or line.strip() == ""
                        or line.startswith("#")
                    ):
                        import_lines.append(line)
                    else:
                        in_imports = False
                        other_lines.append(line)

                # Add missing imports
                missing_imports = ["from pygfa.graph_element.parser import fragment, gap, edge, group"]

                new_content = "\n".join(import_lines + missing_imports + [""] + other_lines)

                if content != new_content:
                    with open(test_file, "w") as f:
                        f.write(new_content)
                    fixed_files.append(test_file)
                    print(f"Fixed imports in {test_file}")

    return len(fixed_files) > 0


def fix_sample_benchmark_files():
    """Fix sample GFA files to use only GFA1 format."""

    data_dir = "/home/gianluca/Devel/pangenome/pygfa/data"
    sample_files = ["sample1_gfa2.gfa", "sample2_gfa2.gfa", "sample3_gfa2.gfa"]

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
        print(
            "  2. Benchmark system: pixi run python -c \"import sys; sys.path.insert(0, '.'); from test.benchmark_filter import filter_gfa_files; print('Found', len(filter_gfa_files('data', None)), 'benchmark files')\""
        )
    else:
        print("⚠️ No changes needed")


if __name__ == "__main__":
    main()
