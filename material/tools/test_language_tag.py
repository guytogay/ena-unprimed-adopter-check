#!/usr/bin/env python3
from __future__ import annotations

import unittest

from language_tag import language_tag_problem


class LanguageTagTests(unittest.TestCase):
    def test_common_tags_pass(self):
        for value in ("en", "en-US", "zh-Hans-CN", "zh-CN"):
            with self.subTest(value=value):
                self.assertIsNone(language_tag_problem(value))

    def test_malformed_or_normalized_inputs_fail(self):
        for value in ("definitely_not_a_bcp47_tag", "", "en--US", "123", "en_US", "en "):
            with self.subTest(value=value):
                self.assertIsNotNone(language_tag_problem(value))

    def test_control_state_is_not_a_language(self):
        self.assertIsNotNone(language_tag_problem("UNKNOWN"))


if __name__ == "__main__":
    unittest.main()
