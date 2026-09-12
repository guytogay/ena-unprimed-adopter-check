#!/usr/bin/env python3
"""Regression tests for ENA-owned path authority and relocation safety."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
TOOLS = REPO / "tools"


class PathAuthorityTests(unittest.TestCase):
    def run_tool(self, *args):
        return subprocess.run([sys.executable, *map(str, args)], text=True, capture_output=True, encoding="utf-8", errors="replace")

    def init_home(self, home: Path) -> Path:
        result = self.run_tool(
            TOOLS / "ena_init.py",
            "--home", home,
            "--timezone", "Etc/UTC",
            "--language", "en-US",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return home

    @staticmethod
    def replace_paths(home: Path, replacements: dict[str, str]) -> None:
        config = home / "ENA.yaml"
        text = config.read_text(encoding="utf-8")
        for old, new in replacements.items():
            if old not in text:
                raise AssertionError(f"fixture key missing: {old!r}")
            text = text.replace(old, new)
        config.write_text(text, encoding="utf-8")

    @staticmethod
    def fill_rescue(package: Path) -> None:
        rescue = package / "rescue.yaml"
        text = rescue.read_text(encoding="utf-8")
        replacements = {
            "target: UNKNOWN": "target: probe",
            "recovery_actor: UNKNOWN": "recovery_actor: human-operator",
            "where_to_act: UNKNOWN": "where_to_act: probe-workspace",
            "changed: UNKNOWN": "changed: config-file",
            "known_good: UNKNOWN": "known_good: git-base-commit",
            "rollback_action: UNKNOWN": "rollback_action: git-revert-change",
            "automatic_rollback: null": "automatic_rollback: false",
            "restart_or_new_session: UNKNOWN": "restart_or_new_session: new-session",
            "verify_operation: UNKNOWN": "verify_operation: probe-check",
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        rescue.write_text(text, encoding="utf-8")

    def test_initializer_writes_home_relative_machine_paths(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            home = self.init_home(Path(tmpdir) / "home")
            text = (home / "ENA.yaml").read_text(encoding="utf-8")
            self.assertIn("ena_home: .\n", text)
            self.assertIn("  changes: changes\n", text)
            self.assertIn("  records: evolution\n", text)
            self.assertIn("  experience_inbox: evolution/experience\n", text)
            self.assertIn("  speculative_candidates: evolution/candidates/speculative\n", text)
            self.assertIn("  selected_candidates: evolution/candidates/selected\n", text)
            self.assertNotIn(str(home.resolve()), text)

    def test_non_default_declared_paths_are_honored_by_writers_and_gate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            home = self.init_home(Path(tmpdir) / "home")
            self.replace_paths(home, {
                "  changes: changes": "  changes: state/change-packages",
                "  experience_inbox: evolution/experience": "  experience_inbox: state/experience",
                "  speculative_candidates: evolution/candidates/speculative": "  speculative_candidates: state/candidates/speculative",
                "  selected_candidates: evolution/candidates/selected": "  selected_candidates: state/candidates/selected",
            })

            candidate = self.run_tool(
                TOOLS / "candidate_record.py",
                "--home", home,
                "--origin", "dream",
                "--candidate", "probe candidate",
                "--reality-check", "probe reality",
            )
            self.assertEqual(candidate.returncode, 0, candidate.stdout + candidate.stderr)
            candidate_path = Path(candidate.stdout.strip()).resolve()
            self.assertEqual(candidate_path.parent, (home / "state/candidates/speculative").resolve())

            outcome = self.run_tool(
                TOOLS / "candidate_outcome.py",
                candidate_path,
                "--home", home,
                "--outcome", "retain",
                "--evidence", "probe-evidence",
                "--decided-by", "probe-agent",
            )
            self.assertEqual(outcome.returncode, 0, outcome.stdout + outcome.stderr)
            self.assertEqual(
                Path(outcome.stdout.strip()).resolve().parent,
                (home / "state/candidates/selected").resolve(),
            )

            validation = self.run_tool(
                TOOLS / "validate_change.py",
                "--home", home,
                "--name", "probe",
                "--", sys.executable, "-c", "print('ok')",
            )
            self.assertEqual(validation.returncode, 0, validation.stdout + validation.stderr)
            self.assertTrue((home / "state/experience/validation-events.jsonl").is_file())

            scaffold = self.run_tool(
                TOOLS / "change_scaffold.py",
                "--home", home,
                "--name", "probe",
                "--profile", "session",
            )
            self.assertEqual(scaffold.returncode, 0, scaffold.stdout + scaffold.stderr)
            package = Path(scaffold.stdout.strip()).resolve()
            self.assertEqual(package.parent, (home / "state/change-packages").resolve())
            self.fill_rescue(package)
            armed = self.run_tool(TOOLS / "safe_change_state.py", package, "armed")
            self.assertEqual(armed.returncode, 0, armed.stdout + armed.stderr)
            self.assertTrue((package / "transitions.jsonl").is_file())

    def test_path_escape_is_rejected_before_external_write(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            home = self.init_home(root / "home")
            self.replace_paths(
                home,
                {"  speculative_candidates: evolution/candidates/speculative": "  speculative_candidates: ../escape"},
            )
            result = self.run_tool(
                TOOLS / "candidate_record.py",
                "--home", home,
                "--origin", "dream",
                "--candidate", "c",
                "--reality-check", "r",
            )
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("outside the active ENA home", result.stderr)
            self.assertFalse((root / "escape").exists())

    def test_legacy_absolute_pointer_inside_current_home_remains_compatible(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            home = self.init_home(Path(tmpdir) / "home")
            custom = (home / "legacy/custom-speculative").resolve()
            self.replace_paths(home, {
                "ena_home: .": f"ena_home: {home.resolve()}",
                "  speculative_candidates: evolution/candidates/speculative": f"  speculative_candidates: {custom}",
            })
            result = self.run_tool(
                TOOLS / "candidate_record.py",
                "--home", home,
                "--origin", "dream",
                "--candidate", "c",
                "--reality-check", "r",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(Path(result.stdout.strip()).resolve().parent, custom)

    def test_moved_legacy_home_fails_closed_and_never_writes_back_to_old_home(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            old = self.init_home(root / "old-home")
            old_spec = (old / "evolution/candidates/speculative").resolve()
            self.replace_paths(old, {
                "ena_home: .": f"ena_home: {old.resolve()}",
                "  changes: changes": f"  changes: {(old / 'changes').resolve()}",
                "  records: evolution": f"  records: {(old / 'evolution').resolve()}",
                "  experience_inbox: evolution/experience": f"  experience_inbox: {(old / 'evolution/experience').resolve()}",
                "  speculative_candidates: evolution/candidates/speculative": f"  speculative_candidates: {old_spec}",
                "  selected_candidates: evolution/candidates/selected": f"  selected_candidates: {(old / 'evolution/candidates/selected').resolve()}",
            })
            moved = root / "moved-home"
            shutil.copytree(old, moved)
            before = list(old_spec.glob("*.json"))

            result = self.run_tool(
                TOOLS / "candidate_record.py",
                "--home", moved,
                "--origin", "dream",
                "--candidate", "must-not-write-back",
                "--reality-check", "r",
            )
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("relocation mismatch", result.stderr)
            self.assertEqual(before, list(old_spec.glob("*.json")))
            self.assertEqual(list((moved / "evolution/candidates/speculative").glob("*.json")), [])


if __name__ == "__main__":
    unittest.main()
