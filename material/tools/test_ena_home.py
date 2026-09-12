#!/usr/bin/env python3
"""Boundary tests: who may write into an ENA home, and on which clock."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from ena_home import EnaHomeError, home_of_package, require_initialized_home
from timezone_utils import TimezoneUnavailable, load_timezone


REPO = Path(__file__).resolve().parents[1]
TOOLS = REPO / "tools"

RESCUE_FILL = {
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


def alternate_zone() -> str | None:
    """A non-UTC zone that this Host can actually resolve, if one exists."""
    for name in ("Asia/Shanghai", "Europe/Berlin", "America/New_York"):
        try:
            load_timezone(name)
            return name
        except TimezoneUnavailable:
            continue
    return None


ALTERNATE_ZONE = alternate_zone()


class HomeBoundaryTests(unittest.TestCase):
    def run_tool(self, *args):
        return subprocess.run([sys.executable, *map(str, args)], text=True, capture_output=True, encoding="utf-8", errors="replace")

    def init_home(self, home: Path, zone: str = "Etc/UTC") -> Path:
        result = self.run_tool(
            TOOLS / "ena_init.py",
            "--home", home,
            "--timezone", zone,
            "--language", "en-US",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return home

    def ready_home(self, home: Path, zone: str = "Etc/UTC") -> Path:
        result = self.run_tool(
            TOOLS / "ena_init.py",
            "--home", home,
            "--timezone", zone,
            "--language", "en-US",
            "--host-profile", "session",
            "--recovery", "git-revert",
            "--recovery-evidence", "home-boundary:restore-check",
            "--rescuer", "human-operator",
            "--rescuer-evidence", "home-boundary:rescuer-check",
            "--rescuer-type", "human",
            "--verified-minimum",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return home

    def scaffold(self, home: Path, *extra) -> Path:
        result = self.run_tool(
            TOOLS / "change_scaffold.py",
            "--home", home,
            "--name", "probe",
            "--profile", "session",
            *extra,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return Path(result.stdout.strip())

    def fill_rescue(self, package: Path) -> None:
        rescue = package / "rescue.yaml"
        text = rescue.read_text(encoding="utf-8")
        for old, new in RESCUE_FILL.items():
            text = text.replace(old, new)
        rescue.write_text(text, encoding="utf-8")

    def transitions(self, package: Path) -> list[dict]:
        return [
            json.loads(line)
            for line in (package / "transitions.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    @staticmethod
    def stamp_offset(package: Path) -> str:
        """The `+HHMM` suffix of the timestamp that names the package directory."""
        return package.name.split("__")[0][-5:]

    # ---------------------------------------------------------------- boundary

    def test_uninitialized_home_is_refused_before_anything_is_written(self):
        cases = {
            "change_scaffold": ("change_scaffold.py", ["--name", "probe", "--profile", "session"]),
            "candidate_record": (
                "candidate_record.py",
                ["--origin", "dream", "--candidate", "c", "--reality-check", "r"],
            ),
            "validate_change": ("validate_change.py", ["--name", "probe", "--", sys.executable, "-c", "print('ok')"]),
        }
        for label, (tool, extra) in cases.items():
            with self.subTest(tool=label):
                with tempfile.TemporaryDirectory() as tmpdir:
                    home = Path(tmpdir) / "not-initialized"
                    result = self.run_tool(TOOLS / tool, "--home", home, *extra)
                    self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                    self.assertIn("ENA home is not initialized", result.stderr)
                    self.assertFalse(home.exists(), "an uninitialized home must not be created")

    def test_gate_refuses_a_package_without_an_initialized_home(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            package = self.scaffold(self.init_home(tmp / "home"))
            self.fill_rescue(package)

            orphan = tmp / "orphan" / "changes" / package.name
            shutil.copytree(package, orphan)
            result = self.run_tool(TOOLS / "safe_change_state.py", orphan, "armed")
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("ENA home is not initialized", result.stderr)
            self.assertFalse((orphan / "transitions.jsonl").exists())

    def test_gate_refuses_a_package_outside_the_change_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            package = self.scaffold(self.init_home(tmp / "home"))
            loose = tmp / "loose" / package.name
            shutil.copytree(package, loose)

            result = self.run_tool(TOOLS / "safe_change_state.py", loose, "armed")
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("is not a SAFE-CHANGE package", result.stderr)

    def test_unreadable_control_files_fail_closed_everywhere(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir) / "corrupt"
            (home / "changes" / "probe").mkdir(parents=True)
            (home / "ENA.yaml").write_text("this is not: [valid\n  control yaml\n", encoding="utf-8")
            (home / "changes" / "probe" / "status.yaml").write_text(
                "schema_version: '0.3'\nhost_profile: session\nstate: preparing\n", encoding="utf-8"
            )
            (home / "changes" / "probe" / "rescue.yaml").write_text(
                "schema_version: '0.3'\nhost_profile: session\n", encoding="utf-8"
            )
            package = home / "changes" / "probe"

            cases = {
                "change_scaffold": [
                    TOOLS / "change_scaffold.py", "--home", home, "--name", "probe", "--profile", "session",
                ],
                "candidate_record": [
                    TOOLS / "candidate_record.py", "--home", home,
                    "--origin", "dream", "--candidate", "c", "--reality-check", "r",
                ],
                "validate_change": [
                    TOOLS / "validate_change.py", "--home", home,
                    "--name", "probe", "--", sys.executable, "-c", "print('ok')",
                ],
                "safe_change_state": [TOOLS / "safe_change_state.py", package, "armed"],
            }
            for label, command in cases.items():
                with self.subTest(tool=label):
                    result = self.run_tool(*command)
                    self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                    self.assertIn("cannot be safely parsed", result.stderr)

            preflight = self.run_tool(TOOLS / "ena_preflight.py", "--home", home)
            self.assertEqual(preflight.returncode, 2, preflight.stdout + preflight.stderr)
            self.assertIn("cannot be safely parsed", preflight.stdout)

    def test_home_without_canonical_timezone_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir) / "home"
            home.mkdir()
            (home / "ENA.yaml").write_text("schema_version: '0.2'\ncanonical_language: en-US\n", encoding="utf-8")
            with self.assertRaisesRegex(EnaHomeError, "has no canonical_timezone"):
                require_initialized_home(home)

            result = self.run_tool(
                TOOLS / "candidate_record.py",
                "--home", home, "--origin", "dream", "--candidate", "c", "--reality-check", "r",
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("has no canonical_timezone", result.stderr)

    def test_unavailable_zone_fails_closed_instead_of_falling_back_to_utc(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir) / "home"
            home.mkdir()
            (home / "ENA.yaml").write_text(
                "schema_version: '0.2'\ncanonical_timezone: Not/AZone\n", encoding="utf-8"
            )
            with self.assertRaises(EnaHomeError):
                require_initialized_home(home)

            result = self.run_tool(
                TOOLS / "candidate_record.py",
                "--home", home, "--origin", "dream", "--candidate", "c", "--reality-check", "r",
            )
            self.assertEqual(result.returncode, 2)
            self.assertNotIn("candidate-", result.stdout)

    def test_home_of_package_requires_the_change_directory_layout(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            home = self.init_home(tmp / "home")
            package = self.scaffold(home)
            # compare against the resolved home: a Windows temp path can carry an 8.3 short name
            self.assertEqual(home_of_package(package), home.resolve())
            with self.assertRaisesRegex(EnaHomeError, "is not a SAFE-CHANGE package"):
                home_of_package(tmp / "elsewhere" / package.name)

    # ---------------------------------------------------------------- clock

    def test_scaffold_stamps_packages_with_the_home_canonical_timezone(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            home = self.init_home(Path(tmpdir) / "home")
            package = self.scaffold(home)
            self.assertEqual(self.stamp_offset(package), "+0000", package.name)
            self.assertIn("timezone: Etc/UTC", (package / "status.yaml").read_text(encoding="utf-8"))

    def test_scaffold_accepts_an_equivalent_timezone_alias(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            home = self.init_home(Path(tmpdir) / "home")
            package = self.scaffold(home, "--timezone", "UTC")
            self.assertEqual(self.stamp_offset(package), "+0000", package.name)

    @unittest.skipIf(ALTERNATE_ZONE is None, "no non-UTC IANA zone is available on this Host")
    def test_scaffold_rejects_a_foreign_timezone(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            home = self.init_home(Path(tmpdir) / "home", ALTERNATE_ZONE)
            result = self.run_tool(
                TOOLS / "change_scaffold.py",
                "--home", home, "--name", "probe", "--profile", "session",
                "--timezone", "Etc/UTC",
            )
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("does not match", result.stderr)
            self.assertEqual(list((home / "changes").iterdir()), [], "a refused scaffold must not leave a package")

    def test_gate_records_the_home_clock_not_the_host_clock(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            home = self.init_home(Path(tmpdir) / "home")
            package = self.scaffold(home)
            self.fill_rescue(package)
            result = self.run_tool(TOOLS / "safe_change_state.py", package, "armed")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            transition = self.transitions(package)[-1]
            self.assertEqual(transition["timezone"], "Etc/UTC")
            self.assertTrue(transition["at"].endswith("+00:00"), transition["at"])
            self.assertIn("timezone: Etc/UTC", (package / "status.yaml").read_text(encoding="utf-8"))

    @unittest.skipIf(ALTERNATE_ZONE is None, "no non-UTC IANA zone is available on this Host")
    def test_gate_records_the_confirmed_offset_of_a_non_utc_home(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            home = self.init_home(Path(tmpdir) / "home", ALTERNATE_ZONE)
            package = self.scaffold(home)
            self.fill_rescue(package)
            result = self.run_tool(TOOLS / "safe_change_state.py", package, "armed")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            transition = self.transitions(package)[-1]
            offset = datetime.now(load_timezone(ALTERNATE_ZONE)).strftime("%z")
            self.assertEqual(transition["timezone"], ALTERNATE_ZONE)
            self.assertTrue(
                transition["at"].endswith(f"{offset[:3]}:{offset[3:]}"),
                f"{transition['at']} should carry the confirmed {offset} offset of {ALTERNATE_ZONE}",
            )

    # ---------------------------------------------------------------- host-written text

    def test_bom_written_control_files_are_readable(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            home = self.ready_home(Path(tmpdir) / "home")
            for name in ("ENA.yaml", "SYSTEM.yaml"):
                path = home / name
                path.write_text("\ufeff" + path.read_text(encoding="utf-8"), encoding="utf-8")

            preflight = self.run_tool(TOOLS / "ena_preflight.py", "--home", home)
            self.assertEqual(preflight.returncode, 0, preflight.stdout + preflight.stderr)

            candidate = self.run_tool(
                TOOLS / "candidate_record.py",
                "--home", home, "--origin", "dream", "--candidate", "c", "--reality-check", "r",
            )
            self.assertEqual(candidate.returncode, 0, candidate.stdout + candidate.stderr)
            record = json.loads(Path(candidate.stdout.strip()).read_text(encoding="utf-8"))
            self.assertEqual(record["timezone"], "Etc/UTC")


if __name__ == "__main__":
    unittest.main()