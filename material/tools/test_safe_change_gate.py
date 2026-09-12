#!/usr/bin/env python3
"""Tests for the recovery declaration the SAFE-CHANGE gate must enforce."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
TOOLS = REPO / "tools"

RESCUE_FILL = {
    "target: UNKNOWN": "target: probe",
    "recovery_actor: UNKNOWN": "recovery_actor: human-operator",
    "where_to_act: UNKNOWN": "where_to_act: probe-workspace",
    "changed: UNKNOWN": "changed: config-file",
    "known_good: UNKNOWN": "known_good: git-base-commit",
    "restart_or_new_session: UNKNOWN": "restart_or_new_session: new-session",
    "verify_operation: UNKNOWN": "verify_operation: probe-check",
}

HOST_TIMER = "systemd-timer ena-rollback.timer"


class RollbackDeclarationTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.home = self.tmp / "home"
        result = self.run_tool(
            TOOLS / "ena_init.py",
            "--home", self.home,
            "--timezone", "Etc/UTC",
            "--language", "en-US",
            "--host-profile", "session",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        scaffold = self.run_tool(
            TOOLS / "change_scaffold.py",
            "--home", self.home,
            "--name", "probe",
            "--profile", "session",
        )
        self.assertEqual(scaffold.returncode, 0, scaffold.stdout + scaffold.stderr)
        self.package = Path(scaffold.stdout.strip())

    def tearDown(self):
        self._tmp.cleanup()

    def run_tool(self, *args):
        return subprocess.run([sys.executable, *map(str, args)], text=True, capture_output=True, encoding="utf-8", errors="replace")

    def write_rescue(
        self,
        *,
        rollback_action: str = "git-revert-change",
        automatic_rollback: str = "null",
        automatic_rollback_reference: str = "null",
    ) -> None:
        text = (self.package / "rescue.yaml").read_text(encoding="utf-8")
        for old, new in RESCUE_FILL.items():
            text = text.replace(old, new)
        text = text.replace("rollback_action: UNKNOWN", f"rollback_action: {rollback_action}")
        text = text.replace("automatic_rollback: null", f"automatic_rollback: {automatic_rollback}")
        text = text.replace(
            "automatic_rollback_reference: null",
            f"automatic_rollback_reference: {automatic_rollback_reference}",
        )
        (self.package / "rescue.yaml").write_text(text, encoding="utf-8")

    def configure_script(self) -> None:
        (self.package / "rollback.py").write_text(
            "#!/usr/bin/env python3\nprint('restore the previous working state')\n", encoding="utf-8"
        )

    def reset_to_preparing(self) -> None:
        (self.package / "transitions.jsonl").unlink(missing_ok=True)
        status = self.package / "status.yaml"
        status.write_text(
            status.read_text(encoding="utf-8").replace("state: armed", "state: preparing"),
            encoding="utf-8",
        )

    def arm(self):
        return self.run_tool(TOOLS / "safe_change_state.py", self.package, "armed")

    def transition(self) -> dict:
        lines = [
            json.loads(line)
            for line in (self.package / "transitions.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        return lines[-1]

    # ------------------------------------------------- declaration is a declaration

    def test_typo_scalar_blocks_instead_of_meaning_manual(self):
        for value in ("flase", "maybe", "yes", "1"):
            with self.subTest(automatic_rollback=value):
                self.write_rescue(automatic_rollback=value)
                result = self.arm()
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn("is not a declaration", result.stderr)
                self.assertFalse((self.package / "transitions.jsonl").exists())

    def test_true_without_reference_blocks(self):
        self.write_rescue(automatic_rollback="true")
        result = self.arm()
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("automatic_rollback_reference is unresolved", result.stderr)

    def test_false_with_reference_is_contradictory(self):
        self.write_rescue(automatic_rollback="false", automatic_rollback_reference=HOST_TIMER)
        result = self.arm()
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("automatic_rollback is false", result.stderr)

    def test_reference_without_declaration_blocks(self):
        self.write_rescue(automatic_rollback="null", automatic_rollback_reference=HOST_TIMER)
        result = self.arm()
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("automatic_rollback is not declared", result.stderr)

    # ------------------------------------------------- host-native automatic recovery

    def test_host_native_automatic_rollback_arms_without_a_local_script(self):
        for artifact in ("placeholder", "absent"):
            with self.subTest(artifact=artifact):
                self.write_rescue(automatic_rollback="true", automatic_rollback_reference=HOST_TIMER)
                if artifact == "absent":
                    (self.package / "rollback.py").unlink()

                result = self.arm()
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                transition = self.transition()
                self.assertEqual(transition["rollback_mode"], "declared_automatic")
                self.assertEqual(transition["rollback_artifact"], artifact)
                self.assertEqual(transition["automatic_rollback_reference"], HOST_TIMER)
                self.reset_to_preparing()

    # ------------------------------------------------- manual / host-triggered recovery

    def test_manual_declaration_still_arms_and_is_recorded(self):
        self.write_rescue(automatic_rollback="false")
        result = self.arm()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        transition = self.transition()
        self.assertEqual(transition["rollback_mode"], "declared_manual_or_host_triggered")
        self.assertEqual(transition["rollback_artifact"], "placeholder")
        self.assertNotIn("automatic_rollback_reference", transition)

    def test_undeclared_placeholder_cannot_arm(self):
        self.write_rescue(automatic_rollback="null")
        result = self.arm()
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("automatic_rollback: false", result.stderr)
        self.assertFalse((self.package / "transitions.jsonl").exists())

    def test_missing_script_needs_a_declaration_too(self):
        (self.package / "rollback.py").unlink()
        blocked = self.arm()
        self.assertEqual(blocked.returncode, 2, blocked.stdout + blocked.stderr)
        self.assertIn("no rollback.py", blocked.stderr)

        self.write_rescue(automatic_rollback="false")
        armed = self.arm()
        self.assertEqual(armed.returncode, 0, armed.stdout + armed.stderr)
        self.assertEqual(self.transition()["rollback_artifact"], "absent")

    # ------------------------------------------------- package-local script

    def test_configured_script_arms_without_inventing_a_declaration(self):
        self.configure_script()
        self.write_rescue(automatic_rollback="null")
        result = self.arm()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        transition = self.transition()
        self.assertEqual(transition["rollback_mode"], "not_declared")
        self.assertEqual(transition["rollback_artifact"], "configured_script")
        self.assertNotIn("automatic_rollback_reference", transition)

    def test_configured_script_does_not_claim_more_than_measured(self):
        """`configured_script` records a non-placeholder artifact, not proven recovery."""
        self.configure_script()
        self.write_rescue(automatic_rollback="null", rollback_action="python rollback.py")
        result = self.arm()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        transition = self.transition()
        self.assertEqual(transition["rollback_artifact"], "configured_script")
        recorded = json.dumps(transition)
        self.assertNotIn("executable_script", recorded)
        self.assertNotIn("recovery_proven", recorded)

    def test_rollback_action_pointing_at_the_placeholder_is_blocked(self):
        self.write_rescue(rollback_action="python rollback.py", automatic_rollback="false")
        result = self.arm()
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("points at rollback.py", result.stderr)

    def test_unresolved_recovery_facts_still_block_arming(self):
        (self.package / "rescue.yaml").write_text(
            "schema_version: '0.3'\nhost_profile: session\nautomatic_rollback: false\n", encoding="utf-8"
        )
        result = self.arm()
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("rollback_action is unresolved", result.stderr)

    def test_full_lifecycle_keeps_the_declaration_in_history(self):
        self.write_rescue(automatic_rollback="false")
        for state in ("armed", "applied"):
            result = self.run_tool(TOOLS / "safe_change_state.py", self.package, state)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        retained = self.run_tool(
            TOOLS / "safe_change_state.py", self.package, "retained", "--evidence", "probe-validation"
        )
        self.assertEqual(retained.returncode, 0, retained.stdout + retained.stderr)
        self.assertIsNone(self.transition().get("rollback_mode"))
        self.assertIn("state: retained", (self.package / "status.yaml").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
