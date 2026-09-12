#!/usr/bin/env python3

from __future__ import annotations

import unittest

from control_yaml import ControlYamlError, missing, parse_control_yaml, scalar


class ControlYamlTests(unittest.TestCase):
    def test_root_and_one_level_mapping(self) -> None:
        data = parse_control_yaml(
            "minimum_ready: true\n"
            "recovery:\n"
            "  primary: 'git:revert'\n"
        )
        self.assertEqual(scalar(data, "minimum_ready"), "true")
        self.assertEqual(scalar(data, "primary", section="recovery"), "git:revert")

    def test_nested_mapping_is_supported(self) -> None:
        data = parse_control_yaml(
            "communication:\n"
            "  a2a:\n"
            "    agent_card: UNKNOWN\n"
        )
        self.assertEqual(data["communication"]["a2a"]["agent_card"], "UNKNOWN")

    def test_colon_in_unquoted_value_is_preserved(self) -> None:
        data = parse_control_yaml("target: repo:path:with:colons\n")
        self.assertEqual(scalar(data, "target"), "repo:path:with:colons")

    def test_missing_accepts_annotated_unknown_but_not_prefix_lookalikes(self) -> None:
        for value in (
            "UNKNOWN",
            "unknown",
            "UNKNOWN - pending owner confirmation",
            "Unknown: pending owner confirmation",
            "UNKNOWN (draft)",
            "UNKNOWN_BACKUP",
            "UNKNOWN_NOT_CONFIGURED",
        ):
            with self.subTest(value=value):
                self.assertTrue(missing(value))
        for value in (
            "unknownstash-backup",
            "UNKNOWNX",
            "known-unknown-boundary",
        ):
            with self.subTest(value=value):
                self.assertFalse(missing(value))

    def test_duplicate_key_fails_closed(self) -> None:
        with self.assertRaises(ControlYamlError):
            parse_control_yaml("state: preparing\nstate: armed\n")

    def test_odd_indentation_fails_closed(self) -> None:
        with self.assertRaises(ControlYamlError):
            parse_control_yaml("a:\n   b: c\n")

    def test_sequence_fails_closed(self) -> None:
        with self.assertRaises(ControlYamlError):
            parse_control_yaml("items:\n  - one\n")

    def test_multiline_scalar_fails_closed(self) -> None:
        with self.assertRaises(ControlYamlError):
            parse_control_yaml("note: |\n  text\n")


if __name__ == "__main__":
    unittest.main()
