import csv
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from analyze_recovery import FIELDS, read_observations, summarize


def data(records):
    stream = io.StringIO()
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(FIELDS)
    writer.writerows(records)
    return stream.getvalue().encode()


class RecoveryAnalysisTests(unittest.TestCase):
    def test_preserves_interleaved_failure_and_successful_tail(self):
        payload = data([(1, 0, 200, "original", 170, ""),
                        (2, 2, 502, "unavailable", 200, "http-error"),
                        (3, 4, 200, "survivor", 180, ""),
                        (4, 6, 502, "unavailable", 220, "http-error"),
                        (5, 8, 200, "replacement", 190, "")])
        result = summarize(payload)
        self.assertEqual(result["error_observations"]["interleaved_http_200_count"], 1)
        self.assertEqual(result["error_observations"]["first_to_last_span_seconds"], 4)
        self.assertEqual(result["error_observations"]["samples_after_final_error"], 1)
        self.assertTrue(result["error_observations"]["all_samples_after_final_error_http_200"])

    def test_empty_sample_fails_instead_of_reporting_availability(self):
        with self.assertRaisesRegex(ValueError, "no observations"):
            summarize(data([]))

    def test_missing_sample_cannot_silently_pass(self):
        with self.assertRaisesRegex(ValueError, "consecutive"):
            summarize(data([(1, 0, 200, "survivor", 170, ""), (3, 2, 200, "survivor", 180, "")]))

    def test_duplicate_elapsed_start_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            summarize(data([(1, 0, 200, "survivor", 170, ""), (2, 0, 200, "survivor", 180, "")]))

    def test_nonfinite_measurements_are_rejected(self):
        for value in ("NaN", "Infinity", "-1"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                read_observations(data([(1, value, 200, "survivor", 170, "")]))

    def test_failure_without_error_category_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "retain an error"):
            summarize(data([(1, 0, 502, "unavailable", 170, "")]))

    def test_no_successes_has_no_misleading_latency_percentile(self):
        result = summarize(data([(1, 0, 0, "unavailable", 5000, "transport-error")]))
        self.assertEqual(result["no_http_response_count"], 1)
        self.assertIsNone(result["successful_duration_ms"]["p95_nearest_rank"])
        self.assertIsNone(result["error_observations"]["all_samples_after_final_error_http_200"])

    def test_no_errors_has_no_invented_error_window(self):
        result = summarize(data([(1, 0, 200, "survivor", 170, "")]))
        self.assertIsNone(result["error_observations"]["first_to_last_span_seconds"])
        self.assertIsNone(result["error_observations"]["samples_after_final_error"])

    def test_check_cli_fails_for_corrupted_expected_summary(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            payload = data([(1, 0, 200, "survivor", 170, "")])
            (root / "observations.csv").write_bytes(payload)
            wrong = summarize(payload)
            wrong["http_200_count"] = 999
            (root / "summary.json").write_text(json.dumps(wrong))
            result = subprocess.run([sys.executable, str(SCRIPTS / "analyze_recovery.py"), str(root / "observations.csv"), "--check", str(root / "summary.json")], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn("differs", result.stderr)


if __name__ == "__main__":
    unittest.main()
