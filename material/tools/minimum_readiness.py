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
from system_unknowns import (
    MINIMUM_MATERIAL_PATHS,
    canonical_token,
    fact_value,
    requirement_is_usable,
    unknown_entries,
)

SELF_ASSERTED = "SELF_ASSERTED"
RESCUER_TYPES = {"human", "agent", "host"}


def evidence_problem(value: str | None) -> str | None:
    """Validate the bounded evidence reference syntax used by First Use.

    Evidence remains caller-supplied/self-asserted. This validates only that a
    durable, single-line, non-control-state reference was actually supplied; it
    does not authenticate or independently execute the referenced check.
    """
    if value is None:
        return "is missing"
    if value != value.strip() or "\n" in value or "\r" in value:
        return "must be a single-line value without leading/trailing whitespace"
    if not requirement_is_usable(value):
        return f"must be a real evidence reference, not {value!r}"
    return None


def aware_timestamp_problem(value: str | None) -> str | None:
    if value is None:
        return "is missing"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return "is not a valid ISO-8601 timestamp"
    if parsed.tzinfo is None:
        return "must include a timezone offset"
    return None


def verification_problems(system: dict[str, object], section: str) -> list[str]:
    problems: list[str] = []
    confidence = scalar(system, "verification_confidence", section=section)
    if confidence != SELF_ASSERTED:
        problems.append(f"SYSTEM.yaml {section}.verification_confidence must be SELF_ASSERTED")

    evidence = scalar(system, "verification_evidence", section=section)
    evidence_issue = evidence_problem(evidence)
    if evidence_issue:
        problems.append(f"SYSTEM.yaml {section}.verification_evidence {evidence_issue}")

    verified_at = scalar(system, "verified_at", section=section)
    timestamp_issue = aware_timestamp_problem(verified_at)
    if timestamp_issue:
        problems.append(f"SYSTEM.yaml {section}.verified_at {timestamp_issue}")
    return problems


def minimum_fact_problems(system: dict[str, object]) -> list[str]:
    problems: list[str] = []
    recovery = scalar(system, "primary", section="recovery")
    if not requirement_is_usable(recovery):
        problems.append("SYSTEM.yaml has no real recovery.primary")
    else:
        problems.extend(verification_problems(system, "recovery"))

    rescuer = scalar(system, "primary", section="rescue")
    if not requirement_is_usable(rescuer):
        problems.append("SYSTEM.yaml has no real rescue.primary")
    else:
        problems.extend(verification_problems(system, "rescue"))

    rescuer_type = scalar(system, "type", section="rescue")
    if rescuer_type not in RESCUER_TYPES:
        problems.append("SYSTEM.yaml rescue.type must be human, agent, or host")
    return problems


def minimum_lifecycle_problems(system: dict[str, object]) -> list[str]:
    """Check only lifecycle contradictions that concern the fixed minimum.

    The full UNKNOWN lifecycle checker remains separate. Startup/preflight does
    not become a universal gate for unrelated material UNKNOWNs.
    """
    entries, root_problems = unknown_entries(system)
    if root_problems:
        return [f"SYSTEM.yaml {item}" for item in root_problems]

    problems: list[str] = []
    for path in MINIMUM_MATERIAL_PATHS:
        value = fact_value(system, path)
        is_unknown = canonical_token(value) == "UNKNOWN"
        has_entry = path in entries
        if has_entry and not is_unknown:
            problems.append(
                f"SYSTEM.yaml minimum lifecycle contradiction: unknowns.{path} exists while {path} is not UNKNOWN"
            )
        elif is_unknown and not has_entry:
            problems.append(
                f"SYSTEM.yaml material UNKNOWN {path} has no lifecycle entry under unknowns"
            )
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

    ready = scalar(system, "minimum_ready")
    if ready != "true":
        if isinstance(ready, str) and ready.lower() == "true":
            problems.append("SYSTEM.yaml minimum_ready must use the canonical lowercase token true")
        else:
            problems.append("SYSTEM.yaml minimum_ready is not true")
    problems.extend(minimum_lifecycle_problems(system))
    problems.extend(minimum_fact_problems(system))
    problems.extend(freshness_problems(system, now=now))
    return problems
