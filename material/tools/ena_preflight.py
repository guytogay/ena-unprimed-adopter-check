#!/usr/bin/env python3
"""Fail fast when ENA First Use is missing, incomplete or stale."""

from __future__ import annotations

import argparse
from pathlib import Path

from minimum_readiness import preflight_problems


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--home", default="~/.ena")
    args = p.parse_args()

    home = Path(args.home).expanduser().resolve()
    problems = preflight_problems(home)
    if problems:
        print("ENA preflight: REFRESH REQUIRED")
        for item in problems:
            print(f"- {item}")
        print("Apply FIRST-USE.md before ordinary work.")
        return 2

    print("ENA preflight: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
