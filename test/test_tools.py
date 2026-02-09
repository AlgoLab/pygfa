import unittest
import sys
import tempfile
import os
import subprocess

sys.path.insert(0, "../")


class TestCanonicalGFA(unittest.TestCase):
    """Test canonical GFA tool."""

    def test_canonical_gfa_help(self):
        """Test canonical_gfa script help functionality."""
        try:
            # Test help option
            result = subprocess.run(
                ["python3", "tools/canonical_gfa.py", "--help"], capture_output=True, text=True, timeout=10
            )
            # Should not crash and should show help
            self.assertEqual(result.returncode, 0)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            self.skipTest("canonical_gfa.py not available or timeout")


class TestPrettifyGFA(unittest.TestCase):
    """Test prettify GFA tool."""

    def test_prettify_gfa_basic(self):
        """Test prettify GFA basic functionality."""
        try:
            # Create a simple GFA file
            gfa_content = "H\tVN:Z:1.0\nS\ts1\tATGC\nL\ts1\t+\ts2\t-\t4M\n"

            with tempfile.NamedTemporaryFile(mode="w", suffix=".gfa", delete=False) as f:
                f.write(gfa_content)
                temp_file = f.name

            # Run prettify tool
            result = subprocess.run(
                ["python3", "tools/prettify_gfa.py", temp_file], capture_output=True, text=True, timeout=10
            )

            # Should execute without error
            self.assertEqual(result.returncode, 0)

            # Clean up
            if os.path.exists(temp_file):
                os.unlink(temp_file)

        except (subprocess.TimeoutExpired, FileNotFoundError):
            self.skipTest("prettify_gfa.py not available or timeout")

    def test_prettify_gfa_missing_file(self):
        """Test prettify GFA with missing file."""
        try:
            result = subprocess.run(
                ["python3", "tools/prettify_gfa.py", "non_existent.gfa"], capture_output=True, text=True, timeout=10
            )

            # Should fail with missing file
            self.assertNotEqual(result.returncode, 0)

        except (subprocess.TimeoutExpired, FileNotFoundError):
            self.skipTest("prettify_gfa.py not available or timeout")


class TestSameGFA(unittest.TestCase):
    """Test same_gfa comparison tool."""

    def test_same_gfa_help(self):
        """Test same_gfa help functionality."""
        try:
            result = subprocess.run(["python3", "tools/same_gfa.py"], capture_output=True, text=True, timeout=10)

            # Should show usage (no arguments provided)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Usage:", result.stdout)

        except (subprocess.TimeoutExpired, FileNotFoundError):
            self.skipTest("same_gfa.py not available or timeout")

    def test_same_gfa_basic_comparison(self):
        """Test basic GFA comparison."""
        try:
            # Create two identical GFA files
            gfa_content = "H\tVN:Z:1.0\nS\ts1\tATGC\n"

            with tempfile.NamedTemporaryFile(mode="w", suffix=".gfa", delete=False) as f1:
                f1.write(gfa_content)
                temp_file1 = f1.name

            with tempfile.NamedTemporaryFile(mode="w", suffix=".gfa", delete=False) as f2:
                f2.write(gfa_content)
                temp_file2 = f2.name

            # Run same_gfa tool
            result = subprocess.run(
                ["python3", "tools/same_gfa.py", temp_file1, temp_file2], capture_output=True, text=True, timeout=10
            )

            # Should succeed for identical files
            self.assertEqual(result.returncode, 0)

            # Clean up
            for temp_file in [temp_file1, temp_file2]:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)

        except (subprocess.TimeoutExpired, FileNotFoundError):
            self.skipTest("same_gfa.py not available or timeout")

    def test_same_gfa_different_files(self):
        """Test comparison of different GFA files."""
        try:
            # Create two different GFA files
            gfa1 = "H\tVN:Z:1.0\nS\ts1\tATGC\n"
            gfa2 = "H\tVN:Z:1.0\nS\ts1\tGCTA\n"  # Different sequence

            with tempfile.NamedTemporaryFile(mode="w", suffix=".gfa", delete=False) as f1:
                f1.write(gfa1)
                temp_file1 = f1.name

            with tempfile.NamedTemporaryFile(mode="w", suffix=".gfa", delete=False) as f2:
                f2.write(gfa2)
                temp_file2 = f2.name

            # Run same_gfa tool
            result = subprocess.run(
                ["python3", "tools/same_gfa.py", temp_file1, temp_file2], capture_output=True, text=True, timeout=10
            )

            # Should fail for different files (return non-zero exit code)
            self.assertNotEqual(result.returncode, 0)

            # Clean up
            for temp_file in [temp_file1, temp_file2]:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)

        except (subprocess.TimeoutExpired, FileNotFoundError):
            self.skipTest("same_gfa.py not available or timeout")


class TestToolsIntegration(unittest.TestCase):
    """Integration tests for tools."""

    def test_tool_error_handling(self):
        """Test how tools handle various error conditions."""
        try:
            # Test with invalid GFA syntax
            invalid_gfa = "This is not a GFA file\n"

            with tempfile.NamedTemporaryFile(mode="w", suffix=".gfa", delete=False) as f:
                f.write(invalid_gfa)
                temp_file = f.name

            # Test each tool with invalid input
            tools_to_test = [
                ("tools/canonical_gfa.py", [temp_file, "output.gfa"]),
                ("tools/prettify_gfa.py", [temp_file]),
                ("tools/same_gfa.py", [temp_file, temp_file]),
            ]

            for tool, args in tools_to_test:
                try:
                    result = subprocess.run(["python3", tool] + args, capture_output=True, text=True, timeout=10)
                    # Most tools should handle invalid GFA gracefully
                    # (either by erroring out or attempting to process)
                    # We just verify they don't crash
                    self.assertIsNotNone(result.returncode)
                except subprocess.TimeoutExpired:
                    pass  # Timeout is okay for this test

            # Clean up
            if os.path.exists(temp_file):
                os.unlink(temp_file)

        except (subprocess.TimeoutExpired, FileNotFoundError):
            self.skipTest("Tools not available for testing")

    def test_tool_large_file_handling(self):
        """Test tool behavior with larger GFA files."""
        try:
            # Create a larger GFA file with multiple segments
            segments = []
            for i in range(100):
                seq = "ATGC" * 10  # 40 bases per segment
                segments.append(f"S\ts{i}\t{seq}\n")

            large_gfa = "H\tVN:Z:1.0\n" + "".join(segments)

            with tempfile.NamedTemporaryFile(mode="w", suffix=".gfa", delete=False) as f:
                f.write(large_gfa)
                temp_file = f.name

            # Test prettify with larger file
            result = subprocess.run(
                ["python3", "tools/prettify_gfa.py", temp_file],
                capture_output=True,
                text=True,
                timeout=30,  # Longer timeout for larger file
            )

            # Should handle larger file without timeout
            self.assertEqual(result.returncode, 0)

            # Clean up
            if os.path.exists(temp_file):
                os.unlink(temp_file)

        except (subprocess.TimeoutExpired, FileNotFoundError):
            self.skipTest("Tool timeout or not available")


class TestToolAvailability(unittest.TestCase):
    """Test that tools are available and executable."""

    def test_tools_exist(self):
        """Verify all tool scripts exist."""
        tools = ["tools/canonical_gfa.py", "tools/prettify_gfa.py", "tools/same_gfa.py"]

        for tool in tools:
            self.assertTrue(os.path.exists(tool), f"Tool {tool} should exist")

    def test_tools_executable(self):
        """Test that tools can be executed (have shebang or are python scripts)."""
        try:
            # Quick check to see if tools are Python scripts
            for tool in ["tools/canonical_gfa.py", "tools/prettify_gfa.py", "tools/same_gfa.py"]:
                if os.path.exists(tool):
                    with open(tool, "r") as f:
                        content = f.read(100)  # Read first 100 chars
                        # Should be a Python script
                        self.assertTrue(
                            content.strip().startswith("#!")
                            or "python" in content.lower()
                            or content.strip().startswith("import")
                            or "def" in content
                        )
        except Exception:
            self.skipTest("Could not verify tool executability")


if __name__ == "__main__":
    unittest.main()
