#!/usr/bin/env python3
"""Tests for freshness reporting when declared metadata cannot be read."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
TOOLS = REPO / "tools"

NOW = "2026-09-12T03:00:00+08:00"


class FreshnessScanTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.source = self.tmp / "records.jsonl"
        self.report_path = self.tmp / "report.json"

    def tearDown(self):
        self._tmp.cleanup()

    def write_records(self, *records):
        self.source.write_text(
            "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
        )

    def scan(self, *extra):
        result = subprocess.run(
            [
                sys.executable, str(TOOLS / "freshness_scan.py"),
                "--input", str(self.source),
                "--output", str(self.report_path),
                "--now", NOW,
                *extra,
            ],
            text=True,
            capture_output=True,
        encoding="utf-8", errors="replace")
        report = json.loads(self.report_path.read_text(encoding="utf-8")) if self.report_path.is_file() else None
        return result, report

    def record_for(self, report, record_id):
        return next(item for item in report["records"] if item["id"] == record_id)

    # ------------------------------------------------------------------ cases

    def test_unreadable_valid_until_is_not_reported_as_absent_policy(self):
        self.write_records(
            {"id": "broken", "checked_at": "2026-09-01T00:00:00+08:00", "valid_until": "2026/12/31"},
            {"id": "absent", "state": "unknown"},
        )
        result, report = self.scan()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        broken = self.record_for(report, "broken")
        absent = self.record_for(report, "absent")
        self.assertEqual(broken["freshness"], "unknown")
        self.assertEqual(broken["reason"], "unparseable_valid_until")
        self.assertEqual(absent["reason"], "no_explicit_freshness_policy")
        self.assertEqual(
            report["invalid_timestamps"],
            [
                {
                    "source_file": str(self.source),
                    "line": 1,
                    "id": "broken",
                    "field": "valid_until",
                    "value": "2026/12/31",
                }
            ],
        )

    def test_unreadable_valid_until_does_not_fall_back_to_caller_max_age(self):
        self.write_records({"id": "broken", "checked_at": "2026-09-11T00:00:00+08:00", "valid_until": "soon"})
        result, report = self.scan("--max-age-hours", "24")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.record_for(report, "broken")["reason"], "unparseable_valid_until")
        self.assertEqual(report["counts"], {"fresh": 0, "stale": 0, "unknown": 1})

    def test_non_string_timestamp_is_reported_instead_of_crashing(self):
        self.write_records({"id": "number", "checked_at": {"unexpected": "shape"}})
        result, report = self.scan()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.record_for(report, "number")["reason"], "unparseable_checked_at")
        self.assertEqual(report["invalid_timestamps"][0]["field"], "checked_at")

    def test_fail_on_unparseable_gates_the_scan(self):
        self.write_records(
            {"id": "broken", "valid_until": "not-a-date"},
            {"id": "fine", "valid_until": "2026-12-31T00:00:00+08:00"},
        )
        result, report = self.scan("--fail-on-unparseable")

        self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
        self.assertTrue(report["policy"]["fail_on_unparseable"])
        self.assertEqual(report["counts"], {"fresh": 1, "stale": 0, "unknown": 1})

    def test_absent_or_readable_metadata_does_not_gate(self):
        self.write_records(
            {"id": "fine", "valid_until": "2026-12-31T00:00:00+08:00"},
            {"id": "absent", "state": "unknown"},
            {"id": "max-age", "checked_at": "2026-09-11T00:00:00+08:00"},
        )
        result, report = self.scan("--fail-on-unparseable", "--max-age-hours", "24")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(report["invalid_timestamps"], [])
        self.assertEqual(report["counts"], {"fresh": 1, "stale": 1, "unknown": 1})

    def test_stale_gate_still_takes_the_documented_exit_code(self):
        self.write_records({"id": "old", "valid_until": "2026-01-01T00:00:00+08:00"})
        result, report = self.scan("--fail-on-stale")

        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertEqual(report["counts"], {"fresh": 0, "stale": 1, "unknown": 0})

    def test_offsetless_timestamp_is_still_read_as_utc(self):
        self.write_records({"id": "naive", "valid_until": "2026-12-31T00:00:00"})
        result, report = self.scan()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.record_for(report, "naive")["reason"], "explicit_valid_until")
        self.assertEqual(report["invalid_timestamps"], [])


if __name__ == "__main__":
    unittest.main()
