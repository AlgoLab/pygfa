import unittest
import sys
import os
import tempfile
import csv
import subprocess

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "tools"))

import characterize_datasets  # noqa: E402
import recommend_defaults  # noqa: E402


class TestCharacterizeDatasets(unittest.TestCase):

    def test_valid_gfa(self):
        result = characterize_datasets.characterize("data/example_3.gfa")
        self.assertIn("file", result)
        self.assertNotIn("error", result)
        self.assertEqual(result["num_segments"], 3)
        self.assertEqual(result["num_links"], 2)
        self.assertEqual(result["num_paths"], 1)
        self.assertEqual(result["num_walks"], 0)
        self.assertGreater(result["file_size_bytes"], 0)
        self.assertIsInstance(result["gc_content"], float)
        self.assertIsInstance(result["avg_seq_len"], float)

    def test_missing_file(self):
        result = characterize_datasets.characterize("/nonexistent/path_12345.gfa")
        self.assertIn("file", result)
        self.assertIn("error", result)

    def test_empty_gfa_file(self):
        fd, path = tempfile.mkstemp(suffix=".gfa")
        os.close(fd)
        try:
            result = characterize_datasets.characterize(path)
            self.assertIn("file", result)
            self.assertNotIn("error", result)
            self.assertEqual(result["num_segments"], 0)
            self.assertEqual(result["file_size_bytes"], 0)
        finally:
            os.unlink(path)


class TestRecommendDefaults(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_csv(self, name, content):
        path = os.path.join(self.tmpdir, name)
        with open(path, "w", newline="") as f:
            f.write(content)
        return path

    def test_load_data_basic(self):
        path = self._write_csv("test.csv",
            "compression_option,compression_value,uncompressed_length,compressed_length,"
            "encode_time_ms,decode_time_ms,original_gfa\n"
            "compression_segment_names,varint+zstd,1000,100,10.0,5.0,data/t.gfa\n"
            "compression_segment_names,varint+zstd,2000,200,15.0,8.0,data/t2.gfa\n"
        )
        rows = recommend_defaults.load_data(path)
        self.assertEqual(len(rows), 2)
        self.assertAlmostEqual(rows[0]["_ratio"], 10.0)
        self.assertAlmostEqual(rows[1]["_ratio"], 10.0)
        self.assertNotEqual(rows[0]["_throughput"], float("inf"))

    def test_load_data_no_timing(self):
        path = self._write_csv("test_nt.csv",
            "compression_option,compression_value,uncompressed_length,compressed_length,"
            "encode_time_ms,decode_time_ms,original_gfa\n"
            "opt,val,1000,100,0,0,data/t.gfa\n"
        )
        rows = recommend_defaults.load_data(path)
        self.assertEqual(rows[0]["_throughput"], float("inf"))
        self.assertEqual(rows[0]["_total_ms"], 0)

    def test_load_data_empty_timing(self):
        path = self._write_csv("test_empty.csv",
            "compression_option,compression_value,uncompressed_length,compressed_length,"
            "encode_time_ms,decode_time_ms,original_gfa\n"
            "opt,val,500,50,,,data/t.gfa\n"
        )
        rows = recommend_defaults.load_data(path)
        self.assertEqual(rows[0]["_throughput"], float("inf"))

    def test_balanced_score_with_timing(self):
        e = {"throughput_mean": 1000.0, "ratio_mean": 8.0}
        score = recommend_defaults.balanced_score(e, max_throughput=2000.0)
        # score = 8.0 * (1 + log(1000/2000)) ≈ 2.4548
        self.assertAlmostEqual(score, 2.45482, places=4)

    def test_balanced_score_with_inf(self):
        e = {"throughput_mean": float("inf"), "ratio_mean": 8.0}
        score = recommend_defaults.balanced_score(e, max_throughput=float("inf"))
        self.assertEqual(score, 8.0)

    def test_balanced_score_zero_max(self):
        e = {"throughput_mean": 100.0, "ratio_mean": 5.0}
        score = recommend_defaults.balanced_score(e, max_throughput=0.0)
        self.assertEqual(score, 5.0)

    def test_compute_pareto(self):
        encodings = [
            {"encoding": "A", "ratio_mean": 5.0, "decode_ms_mean": 10.0},
            {"encoding": "B", "ratio_mean": 8.0, "decode_ms_mean": 5.0},
            {"encoding": "C", "ratio_mean": 6.0, "decode_ms_mean": 20.0},
            {"encoding": "D", "ratio_mean": 3.0, "decode_ms_mean": 2.0},
        ]
        pareto = recommend_defaults.compute_pareto(encodings)
        names = {e["encoding"] for e in pareto}
        self.assertIn("B", names)
        self.assertIn("D", names)
        self.assertNotIn("A", names)
        self.assertNotIn("C", names)

    def test_compute_pareto_all_filtered(self):
        encodings = [{"encoding": "A", "ratio_mean": 1.0, "decode_ms_mean": 10.0}]
        pareto = recommend_defaults.compute_pareto(encodings)
        self.assertEqual(len(pareto), 1)
        self.assertEqual(pareto[0]["encoding"], "A")

    def test_group_by_option(self):
        rows = [
            {"compression_option": "opt_a", "compression_value": "x"},
            {"compression_option": "opt_a", "compression_value": "y"},
            {"compression_option": "opt_b", "compression_value": "z"},
        ]
        groups = recommend_defaults.group_by_option(rows)
        self.assertEqual(len(groups["opt_a"]), 2)
        self.assertEqual(len(groups["opt_b"]), 1)

    def test_aggregate_by_encoding(self):
        rows = [
            {"compression_value": "v+z", "compression_option": "opt",
             "_ratio": 5.0, "_throughput": 100.0,
             "_encode_ms": 10.0, "_decode_ms": 5.0, "original_gfa": "a"},
            {"compression_value": "v+z", "compression_option": "opt",
             "_ratio": 7.0, "_throughput": 200.0,
             "_encode_ms": 12.0, "_decode_ms": 6.0, "original_gfa": "b"},
        ]
        result = recommend_defaults.aggregate_by_encoding(rows)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["encoding"], "v+z")
        self.assertAlmostEqual(result[0]["ratio_median"], 6.0)
        self.assertEqual(result[0]["num_datasets"], 2)

    def test_aggregate_by_encoding_missing_fields(self):
        rows = [
            {"compression_value": "id", "_ratio": 1.0, "_throughput": float("inf"),
             "_encode_ms": 0.0, "_decode_ms": 0.0, "original_gfa": "x"},
        ]
        result = recommend_defaults.aggregate_by_encoding(rows)
        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(result[0]["ratio_median"], 1.0)
        self.assertEqual(result[0]["encode_ms_mean"], 0)
        self.assertEqual(result[0]["decode_ms_mean"], 0)
        self.assertEqual(result[0]["throughput_mean"], 0)

    def test_group_by_characteristic(self):
        rows = [
            {"gc_content": "0.3", "original_gfa": "a"},
            {"gc_content": "0.4", "original_gfa": "b"},
            {"gc_content": "0.5", "original_gfa": "c"},
            {"gc_content": "0.6", "original_gfa": "d"},
        ]
        buckets = recommend_defaults.group_by_characteristic(rows, "gc_content")
        total = sum(len(v) for v in buckets.values())
        self.assertEqual(total, 4)

    def test_group_by_characteristic_missing_col(self):
        rows = [{"original_gfa": "a"}, {"original_gfa": "b"}]
        buckets = recommend_defaults.group_by_characteristic(rows, "gc_content")
        self.assertIn("all", buckets)
        self.assertEqual(len(buckets["all"]), 2)

    def test_rank_best_ratio(self):
        encodings = [
            {"encoding": "A", "ratio_median": 3.0, "decode_ms_mean": 10.0,
             "throughput_mean": 100.0},
            {"encoding": "B", "ratio_median": 8.0, "decode_ms_mean": 20.0,
             "throughput_mean": 50.0},
        ]
        result = recommend_defaults.rank(encodings, "best-ratio")
        self.assertEqual(result[0]["encoding"], "B")

    def test_rank_best_speed(self):
        encodings = [
            {"encoding": "A", "ratio_median": 3.0, "decode_ms_mean": 10.0,
             "throughput_mean": 100.0},
            {"encoding": "B", "ratio_median": 8.0, "decode_ms_mean": 5.0,
             "throughput_mean": 200.0},
        ]
        result = recommend_defaults.rank(encodings, "best-speed")
        self.assertEqual(result[0]["encoding"], "B")

    def test_rank_pareto(self):
        encodings = [
            {"encoding": "A", "ratio_mean": 5.0, "decode_ms_mean": 10.0,
             "ratio_median": 5.0, "throughput_mean": 100.0},
            {"encoding": "B", "ratio_mean": 8.0, "decode_ms_mean": 5.0,
             "ratio_median": 8.0, "throughput_mean": 200.0},
        ]
        result = recommend_defaults.rank(encodings, "pareto")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["encoding"], "B")


class TestJoinSummaryWithChars(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_join_no_matching(self):
        chardir = os.path.join(self.tmpdir, "chars_empty")
        os.makedirs(chardir)

        csv_path = os.path.join(self.tmpdir, "test.csv")
        with open(csv_path, "w", newline="") as f:
            f.write("original_gfa,compression_option,compression_value\n"
                    "data/test.gfa,opt,val\n")

        script = os.path.join(_ROOT, "workflow", "scripts", "join_summary_with_chars.py")
        with open(csv_path) as stdin:
            result = subprocess.run(
                [sys.executable, script, chardir],
                stdin=stdin,
                capture_output=True, text=True, timeout=10,
            )
        self.assertEqual(result.returncode, 0)
        self.assertIn("num_segments", result.stdout)

    def test_missing_chardir(self):
        csv_path = os.path.join(self.tmpdir, "test.csv")
        with open(csv_path, "w", newline="") as f:
            f.write("original_gfa,compression_option,compression_value\n"
                    "data/test.gfa,a,x\n")

        script = os.path.join(_ROOT, "workflow", "scripts", "join_summary_with_chars.py")
        with open(csv_path) as stdin:
            result = subprocess.run(
                [sys.executable, script, "/nonexistent/dir_xyz"],
                stdin=stdin,
                capture_output=True, text=True, timeout=10,
            )
        self.assertEqual(result.returncode, 0)


class TestAddMetadataColumns(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_add_metadata(self):
        csv_path = os.path.join(self.tmpdir, "input.csv")
        with open(csv_path, "w", newline="") as f:
            f.write("uncompressed_length,compressed_length,section_field\n")
            f.write("1000,100,segment_names\n")
            f.write("500,50,sequences\n")

        script = os.path.join(_ROOT, "workflow", "scripts", "add_metadata_columns.py")
        result = subprocess.run(
            [sys.executable, script,
             "--csv", csv_path,
             "--original-gfa", "data/test.gfa",
             "--block-size", "32768",
             "--option", "compression_segment_names",
             "--encoding", "varint+zstd"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0)

        with open(csv_path, newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            self.assertEqual(len(rows), 2)
            for row in rows:
                self.assertEqual(row["original_gfa"], "data/test.gfa")
                self.assertEqual(row["block_size"], "32768")
                self.assertEqual(row["compression_option"], "compression_segment_names")
                self.assertEqual(row["compression_value"], "varint+zstd")


if __name__ == "__main__":
    unittest.main()
