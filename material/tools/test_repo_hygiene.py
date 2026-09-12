#!/usr/bin/env python3
"""Fail when tracked repository files match known temporary/local-only signatures."""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ALLOWED_ENV_FILES = {".env.example", ".env.sample", ".env.template"}
BANNED_SUFFIXES = {".pyc", ".tmp", ".temp", ".bak", ".swp", ".swo", ".orig"}
TEMP_MARKER_ENDINGS = ("-TEMP", "_TEMP", ".TEMP")


def tracked_paths(repo: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    return [Path(item.decode("utf-8")) for item in result.stdout.split(b"\0") if item]


def basename_without_suffixes(path: Path) -> str:
    suffixes = path.suffixes
    if not suffixes:
        return path.name
    return path.name[: -sum(len(suffix) for suffix in suffixes)]


def violation_reason(path: Path) -> str | None:
    name = path.name
    upper = name.upper()
    stem_upper = basename_without_suffixes(path).upper()
    suffixes = {suffix.lower() for suffix in path.suffixes}

    if "__pycache__" in path.parts:
        return "tracked Python bytecode cache"
    if name == ".DS_Store":
        return "tracked macOS metadata file"
    if suffixes & BANNED_SUFFIXES or name.endswith("~"):
        return "tracked temporary/editor backup file"
    if stem_upper == "TEMP" or stem_upper.endswith(TEMP_MARKER_ENDINGS):
        return "tracked temporary marker file"
    if (name == ".env" or name.startswith(".env.")) and name not in ALLOWED_ENV_FILES:
        return "tracked environment file; keep secrets/local configuration out of the repository"
    return None


class RepositoryHygieneTests(unittest.TestCase):
    def test_known_bad_signatures_are_detected(self):
        cases = [
            "LICENSE-README-TEMP",
            "notes-TEMP.md",
            "report_TEMP.txt",
            "TEMP.yaml",
            "draft.tmp.md",
            "session.temp.yaml",
            "data.bak.json",
            "config.orig.md",
            "scratch.tmp",
            "backup.bak",
            "module/__pycache__/x.pyc",
            ".DS_Store",
            ".env",
            ".env.local",
        ]
        for raw in cases:
            with self.subTest(path=raw):
                self.assertIsNotNone(violation_reason(Path(raw)))

    def test_legitimate_near_matches_are_not_rejected(self):
        cases = [
            "TEMPLATE.md",
            "docs/SESSION-TEMPLATE.md",
            "docs/TEMPORARY-NOTES.md",
            "attempt.md",
            "report_template.txt",
            "archive.origami.json",
            ".env.example",
            ".env.sample",
            ".env.template",
        ]
        for raw in cases:
            with self.subTest(path=raw):
                self.assertIsNone(violation_reason(Path(raw)))

    def test_tracked_files_do_not_match_known_local_or_temp_signatures(self):
        repo = Path(__file__).resolve().parents[1]
        violations = []
        for path in tracked_paths(repo):
            reason = violation_reason(path)
            if reason:
                violations.append(f"{path.as_posix()}: {reason}")

        self.assertFalse(
            violations,
            "repository hygiene violations:\n" + "\n".join(violations),
        )


if __name__ == "__main__":
    unittest.main()
