#!/usr/bin/env python3
from __future__ import annotations

import re
import unittest
from pathlib import Path

from control_yaml import ControlYamlError, parse_control_yaml


REPO = Path(__file__).resolve().parents[1]
CONTROL_DOCS = (
    REPO / "A2A.md",
    REPO / "FIRST-USE.md",
    REPO / "examples/change/SESSION-GIT-WORKTREE.md",
)
YAML_FENCE = re.compile(r"```yaml\s*\n(.*?)```", re.DOTALL)


class DocumentedControlYamlTests(unittest.TestCase):
    def test_adopter_control_yaml_examples_are_reader_compatible(self):
        seen = 0
        for path in CONTROL_DOCS:
            text = path.read_text(encoding="utf-8")
            for index, match in enumerate(YAML_FENCE.finditer(text), start=1):
                seen += 1
                with self.subTest(path=str(path.relative_to(REPO)), block=index):
                    try:
                        parse_control_yaml(match.group(1))
                    except ControlYamlError as exc:
                        self.fail(f"documented YAML is not accepted by control_yaml.py: {exc}")
        self.assertGreater(seen, 0, "control-document YAML test found no fenced examples")


if __name__ == "__main__":
    unittest.main()
