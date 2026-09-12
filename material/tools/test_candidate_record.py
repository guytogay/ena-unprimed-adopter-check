#!/usr/bin/env python3
"""Regression tests for speculative candidate artifact safety."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class CandidateRecordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = Path(__file__).resolve().parents[1]
        cls.tool = cls.repo / "tools" / "candidate_record.py"

    def run_candidate(self, home: Path, label: str, *, env=None):
        return subprocess.run(
            [
                sys.executable,
                str(self.tool),
                "--home", str(home),
                "--origin", "dream",
                "--candidate", label,
                "--reality-check", "bounded real task",
            ],
            text=True,
            capture_output=True,
            env=env,
        encoding="utf-8", errors="replace")

    def test_rapid_candidates_are_all_preserved(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir) / "ena"
            home.mkdir()
            (home / "ENA.yaml").write_text(
                "canonical_timezone: Etc/UTC\n",
                encoding="utf-8",
            )

            paths = []
            for index in range(4):
                result = self.run_candidate(home, f"candidate-{index}")
                self.assertEqual(result.returncode, 0, result.stderr)
                paths.append(Path(result.stdout.strip()))

            self.assertEqual(len(set(paths)), 4)
            files = sorted((home / "evolution" / "candidates" / "speculative").glob("*.json"))
            self.assertEqual(len(files), 4)
            self.assertEqual(
                {json.loads(path.read_text(encoding="utf-8"))["candidate"] for path in files},
                {f"candidate-{index}" for index in range(4)},
            )

    def test_canonical_timezone_does_not_depend_on_host_local_timezone(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir) / "ena"
            home.mkdir()
            (home / "ENA.yaml").write_text(
                "canonical_timezone: Etc/UTC\n",
                encoding="utf-8",
            )
            env = os.environ.copy()
            env["TZ"] = "Pacific/Honolulu"

            result = self.run_candidate(home, "timezone-test", env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            record = json.loads(Path(result.stdout.strip()).read_text(encoding="utf-8"))
            self.assertEqual(record["timezone"], "Etc/UTC")
            self.assertTrue(record["created_at"].endswith("+00:00"))

    def test_uninitialized_home_fails_without_creating_candidate_tree(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir) / "missing"
            result = self.run_candidate(home, "should-not-write")
            self.assertEqual(result.returncode, 2)
            self.assertIn("ENA home is not initialized", result.stderr)
            self.assertFalse((home / "evolution").exists())


if __name__ == "__main__":
    unittest.main()
