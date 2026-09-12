#!/usr/bin/env python3
"""Fail fast when ENA First Use is missing, incomplete or stale."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from control_yaml import ControlYamlError, parse_control_yaml, scalar
from ena_home import EnaHomeError, require_initialized_home
from ena_text import read_text
from system_unknowns import requirement_is_usable


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--home", default="~/.ena")
    args = p.parse_args()

    home = Path(args.home).expanduser().resolve()
    config = home / "ENA.yaml"
    system = home / "SYSTEM.yaml"

    problems: list[str] = []
    if not config.exists():
        problems.append(f"missing {config}")
    else:
        try:
            require_initialized_home(home)
        except EnaHomeError as exc:
            problems.append(str(exc))
    if not system.exists():
        problems.append(f"missing {system}")

    if system.exists():
        try:
            data = parse_control_yaml(read_text(system))
        except (OSError, UnicodeError, ControlYamlError) as exc:
            problems.append(f"SYSTEM.yaml cannot be safely parsed: {exc}")
            data = {}

        ready = (scalar(data, "minimum_ready") or "").lower()
        if ready != "true":
            problems.append("SYSTEM.yaml minimum_ready is not true")

        recovery = scalar(data, "primary", section="recovery")
        if not requirement_is_usable(recovery):
            problems.append("SYSTEM.yaml has no real recovery.primary")

        rescuer = scalar(data, "primary", section="rescue")
        if not requirement_is_usable(rescuer):
            problems.append("SYSTEM.yaml has no real rescue.primary")

        valid_until = scalar(data, "valid_until")
        if not valid_until:
            problems.append("SYSTEM.yaml has no valid_until")
        else:
            try:
                deadline = datetime.fromisoformat(valid_until.replace("Z", "+00:00"))
                if deadline.tzinfo is None:
                    problems.append("SYSTEM.yaml valid_until must include a timezone offset")
                elif datetime.now(deadline.tzinfo) > deadline:
                    problems.append(f"SYSTEM.yaml expired at {deadline.isoformat()}")
            except ValueError:
                problems.append("SYSTEM.yaml valid_until is not a valid ISO-8601 timestamp")

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
