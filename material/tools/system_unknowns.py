#!/usr/bin/env python3
"""Validate lifecycle metadata for material UNKNOWN facts in SYSTEM.yaml.

The fact itself stays `UNKNOWN`. Lifecycle state lives under `unknowns.<fact-path>`
so `STALLED_UNKNOWN` never masquerades as a known fact value.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from control_yaml import ControlYamlError, missing, parse_control_yaml
from ena_text import read_text

UNKNOWN = "UNKNOWN"
STALLED_UNKNOWN = "STALLED_UNKNOWN"
UNKNOWN_STATES = {UNKNOWN, STALLED_UNKNOWN}
DISTINCT_NONREADY_STATES = {"UNAVAILABLE", "NOT_NEEDED", "NOT_APPLICABLE", "DEFERRED"}
NONREADY_REQUIREMENT_STATES = UNKNOWN_STATES | DISTINCT_NONREADY_STATES
REQUIRED_METADATA = ("state", "reason", "resolution_path", "owner", "revisit_by", "last_attempt_at")
MINIMUM_MATERIAL_PATHS = ("recovery.primary", "rescue.primary")

INITIAL_UNKNOWN_TEXT = {
    "recovery.primary": (
        "No verified recovery path was supplied to First Use.",
        "Inspect or establish one external recovery mechanism, verify it, then update recovery.primary.",
    ),
    "rescue.primary": (
        "No verified rescuer was supplied to First Use.",
        "Identify a human, Agent, or Host rescuer, verify reachability, then update rescue.primary.",
    ),
}


def canonical_token(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text.upper() if text else None


def requirement_is_usable(value: str | None) -> bool:
    """Whether a required recovery/rescue reference is a real usable declaration.

    Only ENA's canonical control tokens receive special meaning. Arbitrary strings
    such as `TBD`, `unset` or `n/a` are ordinary literals, not a growing synonym list.
    Callers must not use those literals dishonestly to satisfy a requirement.
    """
    if missing(value):
        return False
    token = canonical_token(value)
    return bool(token and token not in NONREADY_REQUIREMENT_STATES)


def fact_value(data: Mapping[str, Any], path: str) -> str | None:
    node: Any = data
    for part in path.split("."):
        if not isinstance(node, Mapping) or part not in node:
            return None
        node = node[part]
    return node if isinstance(node, str) else None


def unknown_entries(data: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]:
    raw = data.get("unknowns")
    if raw is None or raw == "[]":
        return {}, []
    if isinstance(raw, dict):
        return raw, []
    return {}, ["unknowns must be a mapping of fact paths, or [] when no material UNKNOWN is registered"]


def _parse_aware_timestamp(value: str, label: str, problems: list[str]) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        problems.append(f"{label} is not a valid ISO-8601 timestamp")
        return None
    if parsed.tzinfo is None:
        problems.append(f"{label} must include a timezone offset")
        return None
    return parsed


def _meaningful_metadata(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    token = value.strip().upper()
    return token not in UNKNOWN_STATES | DISTINCT_NONREADY_STATES | {"NULL", "NONE", "~", "[]"}


def validate_system_unknowns(
    data: Mapping[str, Any], *, now: datetime | None = None,
    required_material_paths: tuple[str, ...] = MINIMUM_MATERIAL_PATHS,
) -> list[str]:
    """Return contract violations without mutating SYSTEM.yaml.

    `required_material_paths` are the small fixed First Use minimum. Other UNKNOWN
    facts become material only when the Host/Agent explicitly registers them under
    `unknowns`; this avoids turning every unknown capability into universal ceremony.
    """
    problems: list[str] = []
    entries, root_problems = unknown_entries(data)
    problems.extend(root_problems)
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must include a timezone offset")

    for path in required_material_paths:
        value = fact_value(data, path)
        if missing(value):
            if canonical_token(value) != UNKNOWN:
                problems.append(f"{path} is unresolved and must use the canonical fact value UNKNOWN")
            if path not in entries:
                problems.append(f"material UNKNOWN {path} has no lifecycle entry under unknowns")

    for path, entry in entries.items():
        if not isinstance(path, str) or not path.strip():
            problems.append("unknowns contains an empty/non-string fact path")
            continue
        value = fact_value(data, path)
        if canonical_token(value) != UNKNOWN:
            problems.append(
                f"unknowns.{path} exists but the current fact is not exactly UNKNOWN; "
                "remove the lifecycle entry when the fact becomes known or another established state"
            )
        if not isinstance(entry, dict):
            problems.append(f"unknowns.{path} must be a mapping")
            continue

        missing_fields = [field for field in REQUIRED_METADATA if field not in entry]
        if missing_fields:
            problems.append(f"unknowns.{path} is missing: {', '.join(missing_fields)}")
            continue

        state = entry.get("state")
        if state not in UNKNOWN_STATES:
            problems.append(f"unknowns.{path}.state must be UNKNOWN or STALLED_UNKNOWN")

        for field in ("reason", "resolution_path", "owner"):
            if not _meaningful_metadata(entry.get(field)):
                problems.append(f"unknowns.{path}.{field} must contain a real non-placeholder value")

        revisit_raw = entry.get("revisit_by")
        attempt_raw = entry.get("last_attempt_at")
        revisit = None
        attempt = None
        if isinstance(revisit_raw, str):
            revisit = _parse_aware_timestamp(revisit_raw, f"unknowns.{path}.revisit_by", problems)
        else:
            problems.append(f"unknowns.{path}.revisit_by must be a string timestamp")
        if isinstance(attempt_raw, str):
            attempt = _parse_aware_timestamp(attempt_raw, f"unknowns.{path}.last_attempt_at", problems)
        else:
            problems.append(f"unknowns.{path}.last_attempt_at must be a string timestamp")

        if revisit is not None and attempt is not None:
            if revisit <= attempt:
                problems.append(f"unknowns.{path}.revisit_by must be later than last_attempt_at")
            if state == UNKNOWN and now > revisit:
                problems.append(
                    f"unknowns.{path} passed revisit_by without a newer attempt; "
                    "mark lifecycle state STALLED_UNKNOWN or record a real new attempt and next revisit"
                )

    return problems


def initial_material_unknowns(
    *, recovery: str, rescuer: str, checked_at: datetime, revisit_by: datetime, owner: str = "agent"
) -> dict[str, dict[str, str]]:
    """Create truthful First Use metadata only for unresolved minimum facts.

    The initializer has inspected its supplied policy/input surface. When a required
    value is absent it cannot verify an arbitrary Host mechanism itself, so the
    missing supplied value plus the concrete next inspection path form the bounded
    resolution attempt recorded at `checked_at`.
    """
    values = {"recovery.primary": recovery, "rescue.primary": rescuer}
    entries: dict[str, dict[str, str]] = {}
    for path, value in values.items():
        if canonical_token(value) != UNKNOWN:
            continue
        reason, resolution_path = INITIAL_UNKNOWN_TEXT[path]
        entries[path] = {
            "state": UNKNOWN,
            "reason": reason,
            "resolution_path": resolution_path,
            "owner": owner,
            "revisit_by": revisit_by.isoformat(),
            "last_attempt_at": checked_at.isoformat(),
        }
    return entries


def render_unknowns_yaml(entries: Mapping[str, Mapping[str, str]]) -> str:
    if not entries:
        return "unknowns: []\n"
    lines = ["unknowns:"]
    for path, entry in entries.items():
        lines.append(f"  {path}:")
        for field in REQUIRED_METADATA:
            lines.append(f"    {field}: {json.dumps(entry[field], ensure_ascii=False)}")
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description="Validate material UNKNOWN lifecycle metadata in SYSTEM.yaml.")
    p.add_argument("--home", default="~/.ena")
    p.add_argument("--now", help="Override current time with an offset-aware ISO-8601 timestamp (testing/replay).")
    args = p.parse_args()

    system = Path(args.home).expanduser().resolve() / "SYSTEM.yaml"
    try:
        data = parse_control_yaml(read_text(system))
    except (OSError, UnicodeError, ControlYamlError) as exc:
        print(f"ENA UNKNOWN lifecycle: ERROR: cannot read SYSTEM.yaml safely: {exc}")
        return 2

    now = None
    if args.now:
        problems: list[str] = []
        now = _parse_aware_timestamp(args.now, "--now", problems)
        if problems or now is None:
            for item in problems:
                print(f"ENA UNKNOWN lifecycle: ERROR: {item}")
            return 2

    problems = validate_system_unknowns(data, now=now)
    if problems:
        print("ENA UNKNOWN lifecycle: INVALID")
        for item in problems:
            print(f"- {item}")
        return 2

    entries, _ = unknown_entries(data)
    stalled = sum(
        1 for entry in entries.values()
        if isinstance(entry, dict) and entry.get("state") == STALLED_UNKNOWN
    )
    print(f"ENA UNKNOWN lifecycle: OK ({len(entries)} material, {stalled} stalled)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
