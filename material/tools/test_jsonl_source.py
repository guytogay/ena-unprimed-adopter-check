#!/usr/bin/env python3
"""Tests for the shared fail-closed JSONL source reader."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from jsonl_source import JsonlSourceError, load_jsonl_source


class JsonlSourceTests(unittest.TestCase):
    def test_missing_source_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            missing = Path(tmpdir) / "missing.jsonl"
            with self.assertRaisesRegex(JsonlSourceError, "input source not found"):
                load_jsonl_source(missing)

    def test_invalid_json_reports_line(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "bad.jsonl"
            path.write_text('{"id":"a"}\nnot-json\n', encoding="utf-8")
            with self.assertRaisesRegex(JsonlSourceError, "line 2"):
                load_jsonl_source(path)

    def test_existing_empty_source_is_explicitly_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "empty.jsonl"
            path.write_text("", encoding="utf-8")
            source = load_jsonl_source(path)
            self.assertEqual(source.records, [])
            self.assertEqual(len(source.sha256), 64)

    def test_bom_written_source_is_readable(self):
        """PowerShell 5.1 `Out-File -Encoding UTF8` prepends a BOM; it carries no content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "bom.jsonl"
            path.write_text('\ufeff{"id":"a"}\n{"id":"b"}\n', encoding="utf-8")
            source = load_jsonl_source(path)
            self.assertEqual(source.records, [{"id": "a"}, {"id": "b"}])
            self.assertEqual(source.line_numbers, [1, 2])


if __name__ == "__main__":
    unittest.main()
