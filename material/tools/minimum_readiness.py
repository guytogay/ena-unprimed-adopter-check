#!/usr/bin/env python3
"""Shared First Use readiness predicates.

This module keeps `ena_first_use.py` and `ena_preflight.py` on one definition of
READY / NOT_READY. It evaluates existing authority files; it does not mutate
state or prove external mechanisms.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from control_yaml import scalar
from ena_home import EnaHomeError, read_control, require_initialized_home
from language_tag import language_tag_problem
from system_unknowns import requirement_is_usable


def minimum_fact_problems(system: dict[str, object]) -> list[str]:
    problems: list[str] = []
    recovery = scalar(system, "primary", section="recovery")
    if not requirement_is_usable(recovery):
        problems.append("SYSTEM.yaml has no real recovery.primary")

    rescuer = scalar(system, "primary", section="rescue")
    if not requirement_is_usable(rescuer):
        problems.append("SYSTEM.yaml has no real rescue.primary")
    return problems


def freshness_problems(system: dict[str, object], *, now: datetime | None = None) -> list[str]:
    valid_until = scalar(system, "valid_until")
    if not valid_until:
        return ["SYSTEM.yaml has no valid_until"]
    try:
        deadline = datetime.fromisoformat(valid_until.replace("Z", "+00:00"))
    except ValueError:
        return ["SYSTEM.yaml valid_until is not a valid ISO-8601 timestamp"]
    if deadline.tzinfo is None:
        return ["SYSTEM.yaml valid_until must include a timezone offset"]
    current = now.astimezone(deadline.tzinfo) if now is not None else datetime.now(deadline.tzinfo)
    if current > deadline:
        return [f"SYSTEM.yaml expired at {deadline.isoformat()}"]
    return []


def preflight_problems(home: Path, *, now: datetime | None = None) -> list[str]:
    """Return the same problems `ena_preflight.py` exposes to callers."""
    home = Path(home).expanduser().resolve()
    config = home / "ENA.yaml"
    system_path = home / "SYSTEM.yaml"
    problems: list[str] = []

    if not config.exists():
        problems.append(f"missing {config}")
    else:
        try:
            require_initialized_home(home)
            config_data = read_control(config)
            language = scalar(config_data, "canonical_language")
            language_problem = language_tag_problem(language)
            if language_problem:
                problems.append(f"ENA.yaml canonical_language: {language_problem}")
        except EnaHomeError as exc:
            problems.append(str(exc))

    if not system_path.exists():
        problems.append(f"missing {system_path}")
        return problems

    try:
        system = read_control(system_path)
    except EnaHomeError as exc:
        problems.append(f"SYSTEM.yaml cannot be safely parsed: {exc}")
        return problems

    ready = (scalar(system, "minimum_ready") or "").lower()
    if ready != "true":
        problems.append("SYSTEM.yaml minimum_ready is not true")
    problems.extend(minimum_fact_problems(system))
    problems.extend(freshness_problems(system, now=now))
    return problems
