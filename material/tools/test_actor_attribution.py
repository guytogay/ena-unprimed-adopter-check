#!/usr/bin/env python3
"""Attribution tests: an artifact must say who acted and who asked.

The failure these tests guard against is not a crash: it is a durable artifact that
silently looks locally authored (or unattributed) when the work actually arrived
from another Agent over A2A, or from a scheduled job.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TOOLS = REPO / "tools"
sys.path.insert(0, str(TOOLS))

from control_yaml import parse_control_yaml, scalar  # noqa: E402
from ena_actor import (  # noqa: E402
    SELF_ASSERTED,
    UNKNOWN,
    actor_block,
    actor_yaml_block,
    resolve_actor,
)

PEER_ENV = {"ENA_PEER_CALLER": "pc-dsh", "ENA_PEER_TASK_ID": "task-abc-1"}
LEGACY_PEER_ENV = {"DSH_PEER_CALLER": "pc-dsh", "DSH_PEER_TASK_ID": "task-abc-1"}


def write_home(home: Path) -> Path:
    home.mkdir(parents=True, exist_ok=True)
    (home / "ENA.yaml").write_text(
        "schema_version: '0.2'\nena_home: .\ncanonical_timezone: UTC\n"
        "canonical_language: zh-CN\ntext_encoding: UTF-8\n",
        encoding="utf-8",
    )
    return home


def run(*args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    base = {k: v for k, v in os.environ.items() if not k.startswith(("DSH_PEER_", "ENA_"))}
    base.update(env or {})
    return subprocess.run([sys.executable, *args], text=True, capture_output=True, env=base, encoding="utf-8", errors="replace")


class ResolveActorTests(unittest.TestCase):
    def test_nothing_supplied_is_unknown_not_local(self):
        a = resolve_actor({})
        self.assertEqual(a.executor, UNKNOWN)
        self.assertEqual(a.initiated_by, UNKNOWN)
        self.assertEqual(a.channel, UNKNOWN)
        self.assertIsNone(a.correlation_id)
        self.assertEqual(a.attribution_confidence, UNKNOWN)

    def test_peer_bridge_supplies_initiator_and_channel(self):
        a = resolve_actor(PEER_ENV)
        self.assertEqual(a.initiated_by, "peer:pc-dsh")
        self.assertEqual(a.channel, "a2a")
        self.assertEqual(a.correlation_id, "task-abc-1")
        self.assertEqual(a.attribution_confidence, SELF_ASSERTED)

    def test_host_namespace_variables_are_accepted_as_fallback(self):
        # A Host runtime may filter its own namespace (DSH_*) before the dispatched
        # session sees it; the ENA_* names are primary, these are accepted when present.
        a = resolve_actor(LEGACY_PEER_ENV)
        self.assertEqual(a.initiated_by, "peer:pc-dsh")
        self.assertEqual(a.channel, "a2a")

    def test_explicit_values_win_over_peer_bridge(self):
        a = resolve_actor({**PEER_ENV, "ENA_INITIATED_BY": "owner", "ENA_CHANNEL": "chat"})
        self.assertEqual(a.initiated_by, "owner")
        self.assertEqual(a.channel, "chat")

    def test_blank_values_are_not_attribution(self):
        a = resolve_actor({"ENA_ACTOR_EXECUTOR": "   ", "DSH_PEER_CALLER": ""})
        self.assertEqual(a.executor, UNKNOWN)
        self.assertEqual(a.initiated_by, UNKNOWN)

    def test_yaml_block_round_trips_through_the_strict_reader(self):
        text = actor_yaml_block(resolve_actor({**PEER_ENV, "ENA_ACTOR_EXECUTOR": "lxc-dsh/s1"}))
        data = parse_control_yaml(text)
        self.assertEqual(scalar(data, "executor", section="actor"), "lxc-dsh/s1")
        self.assertEqual(scalar(data, "initiated_by", section="actor"), "peer:pc-dsh")
        self.assertEqual(scalar(data, "channel", section="actor"), "a2a")
        self.assertEqual(scalar(data, "correlation_id", section="actor"), "task-abc-1")

    def test_yaml_block_writes_unknown_rather_than_null(self):
        # the strict reader turns `null` into the string "null"; UNKNOWN stays honest
        text = actor_yaml_block(resolve_actor({}))
        self.assertNotIn("null", text)
        self.assertIn(UNKNOWN, text)

    def test_json_block_writes_unknown_rather_than_null(self):
        block = actor_block(resolve_actor({}))
        self.assertEqual(block["executor"], UNKNOWN)
        self.assertEqual(block["initiated_by"], UNKNOWN)
        self.assertEqual(block["channel"], UNKNOWN)
        self.assertEqual(block["correlation_id"], UNKNOWN)
        self.assertEqual(block["attribution_confidence"], UNKNOWN)
        self.assertNotIn(None, block.values())


class ArtifactAttributionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = write_home(Path(self.tmp.name) / "ena")

    def tearDown(self):
        self.tmp.cleanup()

    def test_scaffold_records_actor_in_status(self):
        r = run(str(TOOLS / "change_scaffold.py"), "--home", str(self.home),
                "--name", "attr", "--profile", "session",
                env={**PEER_ENV, "ENA_ACTOR_EXECUTOR": "lxc-dsh/s1"})
        self.assertEqual(r.returncode, 0, r.stderr)
        package = next((self.home / "changes").iterdir())
        data = parse_control_yaml((package / "status.yaml").read_text(encoding="utf-8"))
        self.assertEqual(scalar(data, "executor", section="actor"), "lxc-dsh/s1")
        self.assertEqual(scalar(data, "initiated_by", section="actor"), "peer:pc-dsh")
        # the pre-existing control keys must survive
        self.assertEqual(scalar(data, "state"), "preparing")

    def test_local_session_records_unknown_initiator(self):
        r = run(str(TOOLS / "change_scaffold.py"), "--home", str(self.home),
                "--name", "local", "--profile", "session")
        self.assertEqual(r.returncode, 0, r.stderr)
        package = next((self.home / "changes").iterdir())
        data = parse_control_yaml((package / "status.yaml").read_text(encoding="utf-8"))
        self.assertEqual(scalar(data, "initiated_by", section="actor"), UNKNOWN)

    def test_candidate_records_actor(self):
        r = run(str(TOOLS / "candidate_record.py"), "--home", str(self.home), "--origin", "work",
                "--candidate", "idea", "--reality-check", "check", env=PEER_ENV)
        self.assertEqual(r.returncode, 0, r.stderr)
        record = json.loads(Path(r.stdout.strip()).read_text(encoding="utf-8"))
        self.assertEqual(record["actor"]["initiated_by"], "peer:pc-dsh")
        self.assertEqual(record["actor"]["channel"], "a2a")
        self.assertEqual(record["actor"]["correlation_id"], "task-abc-1")
        self.assertEqual(record["actor"]["attribution_confidence"], SELF_ASSERTED)

    def test_decision_records_actor_next_to_decided_by(self):
        created = run(str(TOOLS / "candidate_record.py"), "--home", str(self.home), "--origin", "work",
                      "--candidate", "idea", "--reality-check", "check", env=PEER_ENV)
        source = created.stdout.strip()
        decided = run(str(TOOLS / "candidate_outcome.py"), "--home", str(self.home),
                      "--outcome", "retain", "--evidence", "trial", "--decided-by", "owner",
                      source, env=PEER_ENV)
        self.assertEqual(decided.returncode, 0, decided.stderr)
        record = json.loads(Path(decided.stdout.strip()).read_text(encoding="utf-8"))
        self.assertEqual(record["decided_by"], "owner")
        self.assertEqual(record["actor"]["executor"], UNKNOWN)   # not supplied -> not invented
        self.assertEqual(record["actor"]["initiated_by"], "peer:pc-dsh")

    def test_validation_event_records_actor(self):
        r = run(str(TOOLS / "validate_change.py"), "--home", str(self.home), "--name", "t",
                "--", sys.executable, "-c", "raise SystemExit(0)",
                env={**PEER_ENV, "ENA_ACTOR_EXECUTOR": "lxc-dsh/s1"})
        self.assertEqual(r.returncode, 0, r.stderr)
        events = (self.home / "evolution" / "experience" / "validation-events.jsonl")
        record = json.loads(events.read_text(encoding="utf-8").splitlines()[-1])
        self.assertEqual(record["actor"]["executor"], "lxc-dsh/s1")
        self.assertEqual(record["actor"]["initiated_by"], "peer:pc-dsh")

    def test_transition_records_actor_and_status_keeps_latest_writer(self):
        package = self.home / "changes" / "20260912T000000+0800__gate"
        (package / "backup").mkdir(parents=True)
        (package / "status.yaml").write_text(
            "schema_version: '0.3'\nhost_profile: session\nstate: preparing\nupdated_at: x\n"
            "previous_state: null\nlast_evidence: null\ntimezone: UTC\n", encoding="utf-8")
        (package / "rescue.yaml").write_text(
            "schema_version: '0.3'\nhost_profile: session\ntarget: t\nrecovery_actor: human\n"
            "where_to_act: w\nchanged: c\nknown_good: k\nrollback_action: r\n"
            "automatic_rollback: false\nrestart_or_new_session: s\nverify_operation: v\n",
            encoding="utf-8")
        r = run(str(TOOLS / "safe_change_state.py"), str(package), "armed",
                env={**PEER_ENV, "ENA_ACTOR_EXECUTOR": "lxc-dsh/s1"})
        self.assertEqual(r.returncode, 0, r.stderr)
        transition = json.loads((package / "transitions.jsonl").read_text(encoding="utf-8").splitlines()[-1])
        self.assertEqual(transition["actor"]["initiated_by"], "peer:pc-dsh")
        self.assertEqual(transition["actor"]["channel"], "a2a")
        self.assertEqual(transition["from"], "preparing")
        self.assertEqual(transition["to"], "armed")

        status = parse_control_yaml((package / "status.yaml").read_text(encoding="utf-8"))
        for key, value in transition["actor"].items():
            self.assertEqual(scalar(status, key, section="actor"), value)
        self.assertEqual(scalar(status, "state"), "armed")

    def test_non_utc_home_without_tzdata_fails_with_guidance(self):
        """Windows CI has no tzdata: a non-UTC zone must fail closed with guidance,
        not silently fall back to another clock."""
        home = Path(self.tmp.name) / "ena-zoned"
        home.mkdir(parents=True)
        (home / "ENA.yaml").write_text(
            "canonical_timezone: Asia/Shanghai\n", encoding="utf-8")
        r = run(str(TOOLS / "change_scaffold.py"), "--home", str(home),
                "--name", "zoned", "--profile", "session")
        if r.returncode == 0:
            self.skipTest("this Host has tzdata; the failure path is not reachable here")
        self.assertIn("tzdata", r.stderr)

    def test_actor_helper_prints_resolved_block(self):
        r = run(str(TOOLS / "ena_actor.py"), env=PEER_ENV)
        self.assertEqual(r.returncode, 0, r.stderr)
        block = json.loads(r.stdout)
        self.assertEqual(block["initiated_by"], "peer:pc-dsh")


if __name__ == "__main__":
    unittest.main(verbosity=2)
