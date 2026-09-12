#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from control_yaml import parse_control_yaml


REPO = Path(__file__).resolve().parents[1]
TOOLS = REPO / "tools"


class FirstUseTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.home = self.tmp / "home"

    def tearDown(self):
        self._tmp.cleanup()

    def run_tool(self, name: str, *args: object):
        return subprocess.run(
            [sys.executable, str(TOOLS / name), *map(str, args)],
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )

    def load(self, path: Path) -> dict:
        return parse_control_yaml(path.read_text(encoding="utf-8"))

    def test_no_authority_cold_start_is_not_ready_without_files(self):
        result = self.run_tool("ena_first_use.py", "--home", self.home)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("ENA First Use: NOT_READY", result.stdout)
        self.assertIn("state: UNINITIALIZED", result.stdout)
        self.assertIn("canonical_timezone", result.stdout)
        self.assertIn("canonical_language", result.stdout)
        self.assertFalse((self.home / "ENA.yaml").exists())
        self.assertFalse((self.home / "SYSTEM.yaml").exists())

    def test_malformed_language_is_rejected_before_init_writes(self):
        for value in ("definitely_not_a_bcp47_tag", "", "en--US", "123", "en_US", "en "):
            with self.subTest(value=value):
                home = self.tmp / ("bad-" + str(abs(hash(value))))
                result = self.run_tool(
                    "ena_init.py",
                    "--home", home,
                    "--timezone", "Etc/UTC",
                    "--language", value,
                )
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertFalse((home / "ENA.yaml").exists())
                self.assertFalse((home / "SYSTEM.yaml").exists())

    def test_partial_then_incremental_then_ready_matches_preflight(self):
        first = self.run_tool(
            "ena_first_use.py",
            "--home", self.home,
            "--timezone", "Etc/UTC",
            "--language", "en-US",
        )
        self.assertEqual(first.returncode, 2, first.stdout + first.stderr)
        self.assertIn("state: INITIALIZED_NOT_READY", first.stdout)
        system = self.load(self.home / "SYSTEM.yaml")
        self.assertEqual(system["minimum_ready"], "false")
        self.assertEqual(system["recovery"]["primary"], "UNKNOWN")
        self.assertEqual(system["rescue"]["primary"], "UNKNOWN")
        self.assertEqual(set(system["unknowns"]), {"recovery.primary", "rescue.primary"})

        before = (self.home / "SYSTEM.yaml").read_bytes()
        again = self.run_tool("ena_first_use.py", "--home", self.home)
        self.assertEqual(again.returncode, 2, again.stdout + again.stderr)
        self.assertEqual((self.home / "SYSTEM.yaml").read_bytes(), before)

        recovery = self.run_tool(
            "ena_first_use.py",
            "--home", self.home,
            "--verified-recovery", "git-worktree-revert",
        )
        self.assertEqual(recovery.returncode, 2, recovery.stdout + recovery.stderr)
        system = self.load(self.home / "SYSTEM.yaml")
        self.assertEqual(system["recovery"]["primary"], "git-worktree-revert")
        self.assertEqual(system["rescue"]["primary"], "UNKNOWN")
        self.assertNotIn("recovery.primary", system["unknowns"])
        self.assertIn("rescue.primary", system["unknowns"])

        ready = self.run_tool(
            "ena_first_use.py",
            "--home", self.home,
            "--verified-rescuer", "operator-console",
            "--rescuer-type", "human",
        )
        self.assertEqual(ready.returncode, 0, ready.stdout + ready.stderr)
        self.assertIn("ENA First Use: READY", ready.stdout)
        system = self.load(self.home / "SYSTEM.yaml")
        self.assertEqual(system["minimum_ready"], "true")
        self.assertEqual(system["unknowns"], "[]")

        preflight = self.run_tool("ena_preflight.py", "--home", self.home)
        self.assertEqual(preflight.returncode, 0, preflight.stdout + preflight.stderr)
        self.assertIn("ENA preflight: OK", preflight.stdout)

    def test_complete_trusted_path_can_be_ready_on_first_run(self):
        result = self.run_tool(
            "ena_first_use.py",
            "--home", self.home,
            "--timezone", "Etc/UTC",
            "--language", "zh-Hans-CN",
            "--verified-recovery", "snapshot-42",
            "--verified-rescuer", "peer-console",
            "--rescuer-type", "agent",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("ENA First Use: READY", result.stdout)
        preflight = self.run_tool("ena_preflight.py", "--home", self.home)
        self.assertEqual(preflight.returncode, 0, preflight.stdout + preflight.stderr)


if __name__ == "__main__":
    unittest.main()
