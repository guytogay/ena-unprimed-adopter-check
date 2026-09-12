#!/usr/bin/env python3
"""Black-box regression for reference-tool output-write boundaries.

The test invokes shipped tools as subprocesses. It verifies that nested output
parents are created, blocked parent paths fail with exit 2 and no traceback,
and repeated SAFE-CHANGE scaffolding does not collide on a one-second name.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
EXAMPLES = ROOT / "examples" / "evolution"
PYTHON = sys.executable


def run_tool(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, *args],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


class OutputWriteBoundaryTests(unittest.TestCase):
    def assert_clean_success(self, result: subprocess.CompletedProcess[str], target: Path) -> None:
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertTrue(target.is_file(), f"expected output file: {target}")

    def assert_clean_refusal(self, result: subprocess.CompletedProcess[str]) -> None:
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("ERROR:", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def exercise_output_tool(self, tool: str, common_args: list[str], suffix: str) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            nested = root / "reports" / "nested" / f"result{suffix}"
            ok = run_tool(str(TOOLS / tool), *common_args, "--output", str(nested))
            self.assert_clean_success(ok, nested)

            blocked = root / "blocked"
            blocked.write_text("not a directory\n", encoding="utf-8")
            bad_target = blocked / f"result{suffix}"
            refused = run_tool(str(TOOLS / tool), *common_args, "--output", str(bad_target))
            self.assert_clean_refusal(refused)
            self.assertFalse(bad_target.exists())

    def test_sleep_prepare_output_boundary(self) -> None:
        self.exercise_output_tool(
            "sleep_prepare.py",
            [
                "--experience",
                str(EXAMPLES / "EXPERIENCE.example.jsonl"),
                "--memory",
                str(EXAMPLES / "MEMORY.example.jsonl"),
            ],
            ".json",
        )

    def test_dream_sample_output_boundary(self) -> None:
        self.exercise_output_tool(
            "dream_sample.py",
            ["--memory", str(EXAMPLES / "MEMORY.example.jsonl"), "--seed", "52"],
            ".json",
        )

    def test_combine_dream_material_output_boundary(self) -> None:
        self.exercise_output_tool(
            "combine_dream_material.py",
            ["--memory", str(EXAMPLES / "MEMORY.example.jsonl")],
            ".jsonl",
        )

    def test_freshness_scan_output_boundary(self) -> None:
        self.exercise_output_tool(
            "freshness_scan.py",
            ["--input", str(EXAMPLES / "FRESHNESS.example.jsonl")],
            ".json",
        )

    def test_change_scaffold_repeated_name_is_collision_safe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            init = run_tool(
                str(TOOLS / "ena_init.py"),
                "--home",
                str(home),
                "--timezone",
                "UTC",
                "--language",
                "en-US",
            )
            self.assertEqual(init.returncode, 0, init.stdout + init.stderr)

            command = [
                str(TOOLS / "change_scaffold.py"),
                "--home",
                str(home),
                "--name",
                "probe",
                "--profile",
                "session",
            ]
            first = run_tool(*command)
            second = run_tool(*command)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertNotIn("Traceback", first.stderr + second.stderr)

            first_path = Path(first.stdout.strip()).resolve()
            second_path = Path(second.stdout.strip()).resolve()
            self.assertNotEqual(first_path, second_path)
            self.assertTrue((first_path / "status.yaml").is_file())
            self.assertTrue((second_path / "status.yaml").is_file())


if __name__ == "__main__":
    unittest.main()
