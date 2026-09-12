#!/usr/bin/env python3
"""Tests for immutable candidate outcome recording."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
TOOLS = REPO / "tools"


class CandidateOutcomeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.home = self.tmp / "home"
        init = self.run_tool(
            TOOLS / "ena_init.py",
            "--home", self.home,
            "--timezone", "Etc/UTC",
            "--language", "en-US",
            "--host-profile", "session",
        )
        self.assertEqual(init.returncode, 0, init.stdout + init.stderr)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def run_tool(self, *args, env=None):
        return subprocess.run(
            [sys.executable, *map(str, args)],
            text=True,
            capture_output=True,
            env=env,
        encoding="utf-8", errors="replace")

    def record_candidate(self, *, reality_check: str = "run bounded trial") -> Path:
        result = self.run_tool(
            TOOLS / "candidate_record.py",
            "--home", self.home,
            "--origin", "dream",
            "--candidate", "try the bounded change",
            "--reality-check", reality_check,
            "--source", "dream-run-1",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return Path(result.stdout.strip())

    def decide(self, source: Path, outcome: str, *extra: str, env=None):
        return self.run_tool(
            TOOLS / "candidate_outcome.py",
            source,
            "--home", self.home,
            "--outcome", outcome,
            "--evidence", "trial-evidence-1",
            "--decided-by", "agent-after-reality-contact",
            *extra,
            env=env,
        )

    def test_retain_writes_selected_record_and_preserves_source(self):
        source = self.record_candidate()
        source_text = source.read_text(encoding="utf-8")
        source_record = json.loads(source_text)

        result = self.decide(source, "retain", "--boundary", "production value not yet measured")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        target = Path(result.stdout.strip())
        self.assertEqual(
            target.parent.resolve(),
            (self.home / "evolution" / "candidates" / "selected").resolve(),
        )
        self.assertTrue(source.exists(), "the speculative occurrence must remain immutable")

        decision = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(decision["candidate_id"], source_record["id"])
        self.assertEqual(decision["outcome"], "retain")
        self.assertEqual(decision["selection_status"], "selected")
        self.assertEqual(decision["evidence_refs"], ["trial-evidence-1"])
        self.assertEqual(decision["boundaries"], ["production value not yet measured"])
        self.assertEqual(decision["candidate_snapshot"]["origin"], "dream")
        self.assertEqual(decision["candidate_snapshot"]["source_fragments"], ["dream-run-1"])
        self.assertEqual(
            decision["source"]["sha256"],
            hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
        )

    def test_non_retained_outcomes_are_durable_but_not_selected(self):
        for outcome in ("revise", "reject", "restore"):
            with self.subTest(outcome=outcome):
                source = self.record_candidate()
                result = self.decide(source, outcome)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                target = Path(result.stdout.strip())
                self.assertEqual(
                    target.parent.resolve(),
                    (self.home / "evolution" / "candidates" / "outcomes").resolve(),
                )
                decision = json.loads(target.read_text(encoding="utf-8"))
                self.assertEqual(decision["outcome"], outcome)
                self.assertEqual(decision["selection_status"], "not_selected")
        self.assertEqual(list((self.home / "evolution" / "candidates" / "selected").glob("*.json")), [])

    def test_source_must_be_speculative_artifact_in_this_home(self):
        source = self.record_candidate()
        outside = self.home / "outside.json"
        outside.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        result = self.decide(outside, "retain")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("must be directly under", result.stderr)

    def test_unresolved_reality_check_blocks(self):
        source = self.record_candidate(reality_check="UNKNOWN")
        result = self.decide(source, "retain")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("reality_check is unresolved", result.stderr)

    def test_non_speculative_source_blocks(self):
        source = self.record_candidate()
        record = json.loads(source.read_text(encoding="utf-8"))
        record["truth_status"] = "selected"
        source.write_text(json.dumps(record), encoding="utf-8")
        result = self.decide(source, "retain")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("truth_status must be 'speculative'", result.stderr)

    def test_unresolved_evidence_blocks(self):
        source = self.record_candidate()
        result = self.run_tool(
            TOOLS / "candidate_outcome.py",
            source,
            "--home", self.home,
            "--outcome", "retain",
            "--evidence", "UNKNOWN",
            "--decided-by", "agent",
        )
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("must be resolved", result.stderr)

    def test_second_outcome_for_same_candidate_blocks(self):
        source = self.record_candidate()
        first = self.decide(source, "retain")
        second = self.decide(source, "reject")
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertEqual(second.returncode, 2, second.stdout + second.stderr)
        self.assertIn("already has a recorded outcome", second.stderr)
        selected = list((self.home / "evolution" / "candidates" / "selected").glob("*.json"))
        outcomes = list((self.home / "evolution" / "candidates" / "outcomes").glob("*.json"))
        self.assertEqual(len(selected), 1)
        self.assertEqual(outcomes, [])

    def test_canonical_home_timezone_wins_over_process_timezone(self):
        source = self.record_candidate()
        env = os.environ.copy()
        env["TZ"] = "Asia/Shanghai"
        result = self.decide(source, "retain", env=env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        decision = json.loads(Path(result.stdout.strip()).read_text(encoding="utf-8"))
        self.assertEqual(decision["timezone"], "Etc/UTC")
        self.assertTrue(decision["decided_at"].endswith("+00:00"))

    def test_uninitialized_home_blocks_without_creating_candidate_tree(self):
        other = self.tmp / "uninitialized"
        source = self.record_candidate()
        result = self.run_tool(
            TOOLS / "candidate_outcome.py",
            source,
            "--home", other,
            "--outcome", "retain",
            "--evidence", "evidence",
            "--decided-by", "agent",
        )
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("ENA home is not initialized", result.stderr)
        self.assertFalse((other / "evolution").exists())


if __name__ == "__main__":
    unittest.main()
