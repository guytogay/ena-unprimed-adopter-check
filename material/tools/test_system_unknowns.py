#!/usr/bin/env python3
from __future__ import annotations

import unittest
from datetime import datetime

from control_yaml import parse_control_yaml
from system_unknowns import (
    REQUIRED_METADATA,
    STALLED_UNKNOWN,
    UNKNOWN,
    initial_material_unknowns,
    render_unknowns_yaml,
    requirement_is_usable,
    unknown_entries,
    validate_system_unknowns,
)


def entry(state: str = UNKNOWN, revisit: str = "2026-09-13T00:00:00+00:00") -> dict[str, str]:
    return {
        "state": state,
        "reason": "Host inspection did not establish the fact.",
        "resolution_path": "Inspect the concrete Host source and record the result.",
        "owner": "agent",
        "revisit_by": revisit,
        "last_attempt_at": "2026-09-12T00:00:00+00:00",
    }


class MaterialUnknownTests(unittest.TestCase):
    def test_initializer_metadata_round_trips_through_strict_reader(self):
        checked = datetime.fromisoformat("2026-09-12T00:00:00+00:00")
        revisit = datetime.fromisoformat("2026-09-19T00:00:00+00:00")
        entries = initial_material_unknowns(
            recovery=UNKNOWN,
            rescuer=UNKNOWN,
            checked_at=checked,
            revisit_by=revisit,
        )
        self.assertEqual(set(entries), {"recovery.primary", "rescue.primary"})
        parsed = parse_control_yaml(render_unknowns_yaml(entries))
        round_tripped, problems = unknown_entries(parsed)
        self.assertEqual(problems, [])
        self.assertEqual(set(round_tripped), set(entries))
        for metadata in round_tripped.values():
            self.assertEqual(set(metadata), set(REQUIRED_METADATA))
            self.assertEqual(metadata["state"], UNKNOWN)
            self.assertEqual(metadata["last_attempt_at"], checked.isoformat())
            self.assertEqual(metadata["revisit_by"], revisit.isoformat())

    def test_known_minimum_values_do_not_create_unknown_entries(self):
        checked = datetime.fromisoformat("2026-09-12T00:00:00+00:00")
        revisit = datetime.fromisoformat("2026-09-19T00:00:00+00:00")
        entries = initial_material_unknowns(
            recovery="git-revert",
            rescuer="human-operator",
            checked_at=checked,
            revisit_by=revisit,
        )
        self.assertEqual(entries, {})

    def test_missing_owner_is_invalid(self):
        data = {
            "recovery": {"primary": UNKNOWN},
            "rescue": {"primary": "human"},
            "unknowns": {"recovery.primary": entry()},
        }
        del data["unknowns"]["recovery.primary"]["owner"]
        problems = validate_system_unknowns(data, now=datetime.fromisoformat("2026-09-12T12:00:00+00:00"))
        self.assertTrue(any("owner" in problem for problem in problems))

    def test_overdue_requires_stalled(self):
        data = {
            "recovery": {"primary": UNKNOWN},
            "rescue": {"primary": "human"},
            "unknowns": {"recovery.primary": entry(revisit="2026-09-12T06:00:00+00:00")},
        }
        problems = validate_system_unknowns(data, now=datetime.fromisoformat("2026-09-12T12:00:00+00:00"))
        self.assertTrue(any("STALLED_UNKNOWN" in problem for problem in problems))

    def test_stalled_keeps_fact_unknown(self):
        data = {
            "recovery": {"primary": UNKNOWN},
            "rescue": {"primary": "human"},
            "unknowns": {"recovery.primary": entry(state=STALLED_UNKNOWN, revisit="2026-09-12T06:00:00+00:00")},
        }
        problems = validate_system_unknowns(data, now=datetime.fromisoformat("2026-09-12T12:00:00+00:00"))
        self.assertEqual(problems, [])
        self.assertEqual(data["recovery"]["primary"], UNKNOWN)

    def test_resolved_fact_must_drop_unknown_entry(self):
        data = {
            "recovery": {"primary": "git-revert"},
            "rescue": {"primary": "human"},
            "unknowns": {"recovery.primary": entry()},
        }
        problems = validate_system_unknowns(data, now=datetime.fromisoformat("2026-09-12T12:00:00+00:00"))
        self.assertTrue(any("current fact is not exactly UNKNOWN" in problem for problem in problems))

    def test_nonready_states_do_not_satisfy_minimum(self):
        for value in ("UNKNOWN", "UNAVAILABLE", "NOT_NEEDED", "NOT_APPLICABLE", "DEFERRED", "STALLED_UNKNOWN"):
            self.assertFalse(requirement_is_usable(value))


if __name__ == "__main__":
    unittest.main(verbosity=2)
