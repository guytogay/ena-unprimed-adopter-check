#!/usr/bin/env python3
"""Regression fixtures for ENA.yaml / SYSTEM.yaml fact authority."""
from __future__ import annotations

import hashlib
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from ena_home import EnaHomeError, require_initialized_home
from fact_authority import build_report

REPO = Path(__file__).resolve().parents[1]
TOOLS = REPO / "tools"
NOW = datetime.fromisoformat("2026-09-12T12:00:00+08:00")
FRESH_CHECKED = "2026-09-12T11:00:00+08:00"
FRESH_UNTIL = "2026-09-13T11:00:00+08:00"
STALE_CHECKED = "2026-09-10T11:00:00+08:00"
STALE_UNTIL = "2026-09-11T11:00:00+08:00"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fact(report: dict, name: str) -> dict:
    return next(item for item in report["facts"] if item["fact"] == name)


class FactAuthorityTests(unittest.TestCase):
    def fixture(self, *, ena_backup: str, system_backup: str, checked: str = FRESH_CHECKED,
                valid_until: str = FRESH_UNTIL, ena_zone: str = "Asia/Shanghai",
                system_zone: str = "Asia/Shanghai") -> Path:
        root = Path(self.tmp.name) / "home"
        root.mkdir(parents=True)
        (root / "ENA.yaml").write_text(
            "schema_version: '0.2'\n"
            f"canonical_timezone: {ena_zone}\n"
            "canonical_language: zh-CN\n"
            "recovery:\n"
            "  changes: ~/.ena/changes\n"
            f"  backup_or_snapshot: {ena_backup}\n",
            encoding="utf-8",
        )
        (root / "SYSTEM.yaml").write_text(
            "schema_version: '0.2'\n"
            f"checked_at: {checked}\n"
            f"valid_until: {valid_until}\n"
            f"canonical_timezone: {system_zone}\n"
            "minimum_ready: true\n"
            "recovery:\n"
            "  primary: real-recovery\n"
            f"  backup_or_snapshot: {system_backup}\n"
            "rescue:\n"
            "  primary: human-owner\n",
            encoding="utf-8",
        )
        return root

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_ena_known_system_unknown_never_falls_back_to_legacy_truth(self):
        home = self.fixture(ena_backup="legacy-snapshot", system_backup="UNKNOWN")
        report = build_report(home, now=NOW)
        item = fact(report, "recovery.backup_or_snapshot")
        self.assertEqual(report["system_freshness"]["status"], "fresh")
        self.assertEqual(item["effective"]["source"], "SYSTEM.yaml")
        self.assertEqual(item["effective"]["status"], "unknown")
        self.assertIsNone(item["effective"]["value"])
        self.assertEqual(item["ena"]["value"], "legacy-snapshot")
        self.assertEqual(item["conflict"], "legacy_needs_reconfirmation")

    def test_annotated_unknown_is_not_promoted_to_live_truth(self):
        home = self.fixture(ena_backup="UNKNOWN", system_backup="UNKNOWN")
        system = home / "SYSTEM.yaml"
        system.write_text(
            system.read_text(encoding="utf-8")
            + "communication:\n  human: UNKNOWN - pending owner confirmation\n",
            encoding="utf-8",
        )
        item = fact(build_report(home, now=NOW), "communication.human")
        self.assertFalse(item["system"]["known"])
        self.assertEqual(item["effective"]["status"], "unknown")
        self.assertIsNone(item["effective"]["value"])

    def test_configured_agent_card_and_live_a2a_reachability_are_separate_facts(self):
        home = self.fixture(ena_backup="UNKNOWN", system_backup="UNKNOWN")
        ena = home / "ENA.yaml"
        system = home / "SYSTEM.yaml"
        ena.write_text(
            ena.read_text(encoding="utf-8")
            + "communication:\n  a2a:\n    agent_card: configured-card-ref\n",
            encoding="utf-8",
        )
        system.write_text(
            system.read_text(encoding="utf-8")
            + "communication:\n  a2a_reachability: verified-two-way\n",
            encoding="utf-8",
        )
        report = build_report(home, now=NOW)
        card = fact(report, "a2a.agent_card")
        reachability = fact(report, "a2a.reachability")
        self.assertEqual(card["authority"], "ENA.yaml")
        self.assertEqual(card["effective"]["value"], "configured-card-ref")
        self.assertEqual(card["conflict"], "none")
        self.assertIsNone(reachability["ena"]["path"])
        self.assertEqual(reachability["system"]["path"], "communication.a2a_reachability")
        self.assertEqual(reachability["authority"], "SYSTEM.yaml")
        self.assertEqual(reachability["effective"]["status"], "known")
        self.assertEqual(reachability["effective"]["value"], "verified-two-way")
        self.assertEqual(reachability["conflict"], "none")

    def test_fresh_system_known_wins_while_conflict_stays_visible(self):
        home = self.fixture(ena_backup="legacy-snapshot", system_backup="verified-snapshot")
        report = build_report(home, now=NOW)
        item = fact(report, "recovery.backup_or_snapshot")
        self.assertEqual(item["effective"]["status"], "known")
        self.assertEqual(item["effective"]["value"], "verified-snapshot")
        self.assertEqual(item["conflict"], "legacy_value_conflict")
        self.assertIn("recovery.backup_or_snapshot", report["conflicts"])

    def test_stale_system_known_does_not_fall_back_to_ena(self):
        home = self.fixture(
            ena_backup="legacy-snapshot",
            system_backup="once-verified-snapshot",
            checked=STALE_CHECKED,
            valid_until=STALE_UNTIL,
        )
        report = build_report(home, now=NOW)
        item = fact(report, "recovery.backup_or_snapshot")
        self.assertEqual(report["system_freshness"]["status"], "stale")
        self.assertEqual(item["effective"]["status"], "stale")
        self.assertIsNone(item["effective"]["value"])
        self.assertEqual(item["conflict"], "stale_system_conflict")

    def test_canonical_time_conflict_is_visible_and_clock_tools_fail_closed(self):
        home = self.fixture(
            ena_backup="UNKNOWN",
            system_backup="UNKNOWN",
            ena_zone="Asia/Shanghai",
            system_zone="Etc/UTC",
        )
        report = build_report(home, now=NOW)
        item = fact(report, "canonical_timezone")
        self.assertEqual(item["authority"], "ENA.yaml")
        self.assertEqual(item["effective"]["value"], "Asia/Shanghai")
        self.assertEqual(item["conflict"], "duplicate_value_conflict")
        with self.assertRaisesRegex(EnaHomeError, "canonical_timezone conflict"):
            require_initialized_home(home)

    def test_unreadable_system_blocks_clock_dependent_home_boundary(self):
        home = self.fixture(ena_backup="UNKNOWN", system_backup="UNKNOWN")
        (home / "SYSTEM.yaml").write_text("broken: [control\n  yaml\n", encoding="utf-8")
        with self.assertRaisesRegex(EnaHomeError, "SYSTEM.yaml cannot be safely parsed"):
            require_initialized_home(home)

    def test_report_is_read_only(self):
        home = self.fixture(ena_backup="legacy-snapshot", system_backup="UNKNOWN")
        before = {name: digest(home / name) for name in ("ENA.yaml", "SYSTEM.yaml")}
        report = build_report(home, now=NOW)
        after = {name: digest(home / name) for name in ("ENA.yaml", "SYSTEM.yaml")}
        self.assertFalse(report["rewrite_performed"])
        self.assertEqual(before, after)

    def test_new_initializer_writes_one_authority_per_fact_class(self):
        home = Path(self.tmp.name) / "new-home"
        result = subprocess.run(
            [
                sys.executable, str(TOOLS / "ena_init.py"),
                "--home", str(home),
                "--timezone", "Etc/UTC",
                "--language", "en-US",
                "--host-profile", "session",
            ],
            text=True,
            capture_output=True,
        encoding="utf-8", errors="replace")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        ena_text = (home / "ENA.yaml").read_text(encoding="utf-8")
        system_text = (home / "SYSTEM.yaml").read_text(encoding="utf-8")
        self.assertNotIn("survival:", ena_text)
        self.assertNotIn("backup_or_snapshot:", ena_text)
        self.assertNotIn("rollback_scheduler:", ena_text)
        self.assertNotIn("canonical_timezone:", system_text)
        self.assertNotIn("a2a_agent_card:", system_text)
        self.assertIn("a2a_reachability: UNKNOWN", system_text)


if __name__ == "__main__":
    unittest.main()
