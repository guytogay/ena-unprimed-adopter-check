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

    def init_not_ready(self, home: Path | None = None):
        target = home or self.home
        result = self.run_tool(
            "ena_first_use.py",
            "--home", target,
            "--timezone", "Etc/UTC",
            "--language", "en-US",
        )
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        return target

    def ready_home(self, home: Path | None = None, recovery: str = "snapshot-42", rescuer: str = "operator-console"):
        target = home or self.home
        result = self.run_tool(
            "ena_first_use.py",
            "--home", target,
            "--timezone", "Etc/UTC",
            "--language", "en-US",
            "--verified-recovery", recovery,
            "--recovery-evidence", "restore-drill:ok",
            "--verified-rescuer", rescuer,
            "--rescuer-evidence", "reachability-check:ok",
            "--rescuer-type", "human",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return target

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
        self.init_not_ready()
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
            "--recovery-evidence", "restore-drill:2026-09-13",
        )
        self.assertEqual(recovery.returncode, 2, recovery.stdout + recovery.stderr)
        system = self.load(self.home / "SYSTEM.yaml")
        self.assertEqual(system["recovery"]["primary"], "git-worktree-revert")
        self.assertEqual(system["recovery"]["verification_confidence"], "SELF_ASSERTED")
        self.assertEqual(system["recovery"]["verification_evidence"], "restore-drill:2026-09-13")
        self.assertIn("verified_at", system["recovery"])
        self.assertEqual(system["rescue"]["primary"], "UNKNOWN")
        self.assertNotIn("recovery.primary", system["unknowns"])
        self.assertIn("rescue.primary", system["unknowns"])

        ready = self.run_tool(
            "ena_first_use.py",
            "--home", self.home,
            "--verified-rescuer", "operator-console",
            "--rescuer-evidence", "reachability-check:2026-09-13",
            "--rescuer-type", "human",
        )
        self.assertEqual(ready.returncode, 0, ready.stdout + ready.stderr)
        self.assertIn("ENA First Use: READY", ready.stdout)
        system = self.load(self.home / "SYSTEM.yaml")
        self.assertEqual(system["minimum_ready"], "true")
        self.assertEqual(system["unknowns"], "[]")
        self.assertEqual(system["rescue"]["verification_confidence"], "SELF_ASSERTED")

        preflight = self.run_tool("ena_preflight.py", "--home", self.home)
        self.assertEqual(preflight.returncode, 0, preflight.stdout + preflight.stderr)
        self.assertIn("ENA preflight: OK", preflight.stdout)

    def test_complete_evidenced_path_can_be_ready_on_first_run(self):
        self.ready_home(recovery="x", rescuer="y")
        system = self.load(self.home / "SYSTEM.yaml")
        self.assertEqual(system["recovery"]["primary"], "x")
        self.assertEqual(system["rescue"]["primary"], "y")
        self.assertEqual(system["recovery"]["verification_evidence"], "restore-drill:ok")
        preflight = self.run_tool("ena_preflight.py", "--home", self.home)
        self.assertEqual(preflight.returncode, 0, preflight.stdout + preflight.stderr)

    def test_existing_unverified_scalars_are_not_promoted_or_rewritten(self):
        created = self.run_tool(
            "ena_init.py",
            "--home", self.home,
            "--timezone", "Etc/UTC",
            "--language", "en-US",
            "--recovery", "asdf",
            "--rescuer", "x",
            "--rescuer-type", "human",
        )
        self.assertEqual(created.returncode, 0, created.stdout + created.stderr)
        path = self.home / "SYSTEM.yaml"
        before = path.read_bytes()

        inspected = self.run_tool(
            "ena_first_use.py",
            "--home", self.home,
            "--timezone", "Etc/UTC",
            "--language", "en-US",
        )
        self.assertEqual(inspected.returncode, 2, inspected.stdout + inspected.stderr)
        self.assertIn("NOT_READY", inspected.stdout)
        self.assertEqual(path.read_bytes(), before)
        system = self.load(path)
        self.assertEqual(system["minimum_ready"], "false")
        self.assertNotIn("verification_confidence", system["recovery"])

    def test_minimum_lifecycle_contradiction_fails_closed_without_deleting_evidence(self):
        self.init_not_ready()
        path = self.home / "SYSTEM.yaml"
        text = path.read_text(encoding="utf-8").replace("  primary: UNKNOWN", "  primary: TBD", 1)
        path.write_text(text, encoding="utf-8")
        before = path.read_bytes()

        preflight = self.run_tool("ena_preflight.py", "--home", self.home)
        self.assertEqual(preflight.returncode, 2, preflight.stdout + preflight.stderr)
        self.assertIn("minimum lifecycle contradiction", preflight.stdout)

        inspected = self.run_tool("ena_first_use.py", "--home", self.home)
        self.assertEqual(inspected.returncode, 2, inspected.stdout + inspected.stderr)
        self.assertEqual(path.read_bytes(), before)
        self.assertIn("recovery.primary:", path.read_text(encoding="utf-8"))

    def test_explicit_evidence_can_resolve_the_targeted_lifecycle_contradiction(self):
        self.init_not_ready()
        path = self.home / "SYSTEM.yaml"
        text = path.read_text(encoding="utf-8").replace("  primary: UNKNOWN", "  primary: TBD", 1)
        path.write_text(text, encoding="utf-8")

        result = self.run_tool(
            "ena_first_use.py",
            "--home", self.home,
            "--verified-recovery", "TBD",
            "--recovery-evidence", "operator-check:recovery",
        )
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        system = self.load(path)
        self.assertEqual(system["recovery"]["primary"], "TBD")
        self.assertEqual(system["recovery"]["verification_confidence"], "SELF_ASSERTED")
        self.assertNotIn("recovery.primary", system["unknowns"])
        self.assertIn("rescue.primary", system["unknowns"])

    def test_uppercase_ready_is_rejected_without_silent_normalization(self):
        self.ready_home()
        path = self.home / "SYSTEM.yaml"
        text = path.read_text(encoding="utf-8").replace("minimum_ready: true", "minimum_ready: TRUE", 1)
        path.write_text(text, encoding="utf-8")
        before = path.read_bytes()

        preflight = self.run_tool("ena_preflight.py", "--home", self.home)
        self.assertEqual(preflight.returncode, 2, preflight.stdout + preflight.stderr)
        self.assertIn("canonical lowercase token true", preflight.stdout)

        inspected = self.run_tool("ena_first_use.py", "--home", self.home)
        self.assertEqual(inspected.returncode, 2, inspected.stdout + inspected.stderr)
        self.assertEqual(path.read_bytes(), before)

    def test_evidence_is_required_and_short_aliases_are_removed(self):
        missing_evidence_home = self.tmp / "missing-evidence"
        missing_evidence = self.run_tool(
            "ena_first_use.py",
            "--home", missing_evidence_home,
            "--timezone", "Etc/UTC",
            "--language", "en-US",
            "--verified-recovery", "x",
        )
        self.assertEqual(missing_evidence.returncode, 2, missing_evidence.stdout + missing_evidence.stderr)
        self.assertFalse((missing_evidence_home / "ENA.yaml").exists())

        alias_home = self.tmp / "alias"
        alias = self.run_tool(
            "ena_first_use.py",
            "--home", alias_home,
            "--timezone", "Etc/UTC",
            "--language", "en-US",
            "--recovery", "x",
        )
        self.assertNotEqual(alias.returncode, 0, alias.stdout + alias.stderr)
        self.assertFalse((alias_home / "ENA.yaml").exists())

    def test_initializer_verified_minimum_requires_and_persists_evidence(self):
        rejected_home = self.tmp / "init-rejected"
        rejected = self.run_tool(
            "ena_init.py",
            "--home", rejected_home,
            "--timezone", "Etc/UTC",
            "--language", "en-US",
            "--recovery", "x",
            "--rescuer", "y",
            "--rescuer-type", "human",
            "--verified-minimum",
        )
        self.assertNotEqual(rejected.returncode, 0, rejected.stdout + rejected.stderr)
        self.assertFalse((rejected_home / "ENA.yaml").exists())

        accepted_home = self.tmp / "init-accepted"
        accepted = self.run_tool(
            "ena_init.py",
            "--home", accepted_home,
            "--timezone", "Etc/UTC",
            "--language", "en-US",
            "--recovery", "x",
            "--rescuer", "y",
            "--rescuer-type", "human",
            "--recovery-evidence", "restore:ok",
            "--rescuer-evidence", "reachability:ok",
            "--verified-minimum",
        )
        self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)
        system = self.load(accepted_home / "SYSTEM.yaml")
        self.assertEqual(system["minimum_ready"], "true")
        self.assertEqual(system["recovery"]["verification_confidence"], "SELF_ASSERTED")
        preflight = self.run_tool("ena_preflight.py", "--home", accepted_home)
        self.assertEqual(preflight.returncode, 0, preflight.stdout + preflight.stderr)

    def test_unrelated_unknown_lifecycle_does_not_become_a_startup_gate(self):
        self.ready_home()
        path = self.home / "SYSTEM.yaml"
        text = path.read_text(encoding="utf-8")
        text = text.replace("  host: UNKNOWN", "  host: runtime-x", 1)
        text = text.replace(
            "unknowns: []",
            "unknowns:\n"
            "  runtime.host:\n"
            "    state: UNKNOWN\n"
            "    reason: stale observation\n"
            "    resolution_path: inspect runtime\n"
            "    owner: agent\n"
            "    revisit_by: 2099-01-02T00:00:00+00:00\n"
            "    last_attempt_at: 2099-01-01T00:00:00+00:00",
            1,
        )
        path.write_text(text, encoding="utf-8")
        preflight = self.run_tool("ena_preflight.py", "--home", self.home)
        self.assertEqual(preflight.returncode, 0, preflight.stdout + preflight.stderr)


if __name__ == "__main__":
    unittest.main()
