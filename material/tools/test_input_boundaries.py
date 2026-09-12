#!/usr/bin/env python3
"""Integration tests for reference-tool input and initialization boundaries."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class InputBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = Path(__file__).resolve().parents[1]
        cls.tools = cls.repo / "tools"
        cls.examples = cls.repo / "examples" / "evolution"

    def run_tool(self, *args):
        return subprocess.run([sys.executable, *map(str, args)], text=True, capture_output=True, encoding="utf-8", errors="replace")

    def test_declared_missing_jsonl_sources_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            missing = tmp / "missing.jsonl"

            cases = [
                (
                    self.tools / "sleep_prepare.py",
                    "--experience", self.examples / "EXPERIENCE.example.jsonl",
                    "--memory", missing,
                    "--output", tmp / "sleep.json",
                ),
                (
                    self.tools / "combine_dream_material.py",
                    "--memory", missing,
                    "--output", tmp / "material.jsonl",
                ),
                (
                    self.tools / "dream_sample.py",
                    "--memory", missing,
                    "--output", tmp / "dream.json",
                ),
                (
                    self.tools / "freshness_scan.py",
                    "--input", missing,
                    "--output", tmp / "freshness.json",
                ),
            ]

            for case in cases:
                with self.subTest(tool=Path(case[0]).name):
                    result = self.run_tool(*case)
                    self.assertEqual(result.returncode, 2)
                    self.assertIn("input source not found", result.stderr)

    def test_validate_change_does_not_initialize_ena_home(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir) / "not-initialized"
            result = self.run_tool(
                self.tools / "validate_change.py",
                "--home", home,
                "--name", "boundary-test",
                "--", sys.executable, "-c", "print('ok')",
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("ENA home is not initialized", result.stderr)
            self.assertFalse(home.exists())


if __name__ == "__main__":
    unittest.main()
