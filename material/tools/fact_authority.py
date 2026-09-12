#!/usr/bin/env python3
"""Report stable/live fact authority for an existing ENA home without rewriting it."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from control_yaml import ControlYamlError, missing, parse_control_yaml
from ena_text import read_text

FACTS = (
    ("canonical_timezone", "ena", "canonical_timezone", "canonical_timezone"),
    ("a2a.agent_card", "ena", "communication.a2a.agent_card", "communication.a2a_agent_card"),
    ("a2a.reachability", "system", None, "communication.a2a_reachability"),
    ("runtime.host", "system", "runtime.host", "runtime.host"),
    ("runtime.agent_runtime", "system", "runtime.agent", "runtime.agent_runtime"),
    ("runtime.host_profile", "system", "survival.host_profile", "runtime.host_profile"),
    ("runtime.startup", "system", "runtime.startup", "runtime.startup"),
    ("runtime.restart", "system", "runtime.restart", "runtime.restart"),
    ("communication.human", "system", "communication.human", "communication.human"),
    ("recovery.backup_or_snapshot", "system", "recovery.backup_or_snapshot", "recovery.backup_or_snapshot"),
    ("recovery.scheduler_or_timer", "system", "recovery.rollback_scheduler", "recovery.scheduler_or_timer"),
    ("rescue.primary", "system", "survival.external_escalation", "rescue.primary"),
)


class FactAuthorityError(ValueError):
    pass


def read_control(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FactAuthorityError(f"missing {path}")
    try:
        return parse_control_yaml(read_text(path))
    except (OSError, UnicodeError, ControlYamlError) as exc:
        raise FactAuthorityError(f"{path.name} cannot be safely parsed: {exc}") from exc


def value_at(data: dict[str, Any], dotted: str | None) -> str | None:
    if dotted is None:
        return None
    current: Any = data
    for part in dotted.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current if isinstance(current, str) else None


def known(value: str | None) -> bool:
    return not missing(value)


def parse_time(value: str | None) -> datetime | None:
    if missing(value):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def system_freshness(system: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    checked_raw = value_at(system, "checked_at")
    valid_raw = value_at(system, "valid_until")
    checked = parse_time(checked_raw)
    valid = parse_time(valid_raw)
    if checked is None or valid is None:
        return {"status": "unknown", "checked_at": checked_raw, "valid_until": valid_raw,
                "reason": "missing_or_unparseable_freshness_metadata"}
    if valid < checked:
        return {"status": "unknown", "checked_at": checked_raw, "valid_until": valid_raw,
                "reason": "valid_until_precedes_checked_at"}
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise FactAuthorityError("comparison time must include a timezone offset")
    if instant > valid:
        return {"status": "stale", "checked_at": checked_raw, "valid_until": valid_raw, "reason": "expired"}
    return {"status": "fresh", "checked_at": checked_raw, "valid_until": valid_raw, "reason": None}


def fact_report(name: str, authority: str, ena_path: str | None, system_path: str | None,
                ena: dict[str, Any], system: dict[str, Any], freshness: dict[str, Any]) -> dict[str, Any]:
    ena_value = value_at(ena, ena_path)
    system_value = value_at(system, system_path)
    ena_known = known(ena_value)
    system_known = known(system_value)
    conflict = "none"
    effective_value: str | None = None
    effective_status = "unknown"
    effective_source = "ENA.yaml" if authority == "ena" else "SYSTEM.yaml"

    if authority == "ena":
        if ena_known:
            effective_value, effective_status = ena_value, "known"
        if system_known:
            if ena_known and system_value != ena_value:
                conflict = "duplicate_value_conflict"
            elif not ena_known:
                conflict = "legacy_needs_reconfirmation"
            else:
                conflict = "legacy_duplicate_same_value"
    else:
        state = freshness["status"]
        if state == "fresh":
            if system_known:
                effective_value, effective_status = system_value, "known"
                if ena_known and ena_value != system_value:
                    conflict = "legacy_value_conflict"
                elif ena_known:
                    conflict = "legacy_duplicate_same_value"
            elif ena_known:
                conflict = "legacy_needs_reconfirmation"
        elif state == "stale":
            effective_status = "stale"
            conflict = "stale_system_conflict" if ena_known and system_known and ena_value != system_value else "stale_system"
        else:
            conflict = "system_freshness_unknown"

    return {
        "fact": name,
        "authority": effective_source,
        "ena": {"path": ena_path, "value": ena_value, "known": ena_known},
        "system": {"path": system_path, "value": system_value, "known": system_known},
        "effective": {"source": effective_source, "status": effective_status, "value": effective_value},
        "conflict": conflict,
    }


def build_report(home: Path, *, now: datetime | None = None) -> dict[str, Any]:
    home = Path(home).expanduser().resolve()
    ena = read_control(home / "ENA.yaml")
    system = read_control(home / "SYSTEM.yaml")
    freshness = system_freshness(system, now=now)
    facts = [fact_report(*spec, ena, system, freshness) for spec in FACTS]
    return {
        "schema_version": "0.1",
        "home": str(home),
        "system_freshness": freshness,
        "facts": facts,
        "conflicts": [item["fact"] for item in facts if item["conflict"] != "none"],
        "rewrite_performed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Report ENA/SYSTEM fact authority without rewriting either file.")
    parser.add_argument("--home", default="~/.ena")
    parser.add_argument("--at", help="Aware ISO-8601 comparison time for reproducible inspection")
    args = parser.parse_args()
    now = None
    if args.at:
        now = parse_time(args.at)
        if now is None:
            print("ENA fact authority: ERROR: --at must include a valid timezone offset", file=sys.stderr)
            return 2
    try:
        report = build_report(Path(args.home), now=now)
    except FactAuthorityError as exc:
        print(f"ENA fact authority: ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
