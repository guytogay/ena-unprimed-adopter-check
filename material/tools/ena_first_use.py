#!/usr/bin/env python3
"""Bounded executable First Use path for cold or incremental adoption.

The tool derives state from ENA.yaml + SYSTEM.yaml. It creates no bootstrap
ledger and never persists detected-but-unconfirmed stable settings. Existing
minimum facts are observations, not verification: only an explicit verified
update with evidence may strengthen readiness state.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from control_yaml import scalar
from ena_home import EnaHomeError, read_control, require_initialized_home
from language_tag import language_tag_problem
from minimum_readiness import (
    RESCUER_TYPES,
    SELF_ASSERTED,
    evidence_problem,
    minimum_fact_problems,
    preflight_problems,
)
from system_unknowns import MINIMUM_MATERIAL_PATHS, canonical_token, fact_value, unknown_entries
from timezone_utils import TimezoneUnavailable, load_timezone


def _print_not_ready(state: str, problems: list[str]) -> int:
    print("ENA First Use: NOT_READY")
    print(f"state: {state}")
    for item in problems:
        print(f"- {item}")
    return 2


def _print_ready() -> int:
    print("ENA First Use: READY")
    print("state: READY")
    return 0


def _validate_reference(label: str, value: str | None) -> str | None:
    if value is None:
        return None
    if value != value.strip() or "\n" in value or "\r" in value:
        raise ValueError(f"{label} must be a single-line value without leading/trailing whitespace")
    # Do not grow a natural-language placeholder blacklist here. The proof that
    # a declaration participates in READY is the explicit evidence-bearing
    # update, not whether the scalar looks path-like to ENA.
    from system_unknowns import requirement_is_usable

    if not requirement_is_usable(value):
        raise ValueError(f"{label} must be a caller-verified declaration, not {value!r}")
    return value


def _render_control_mapping(data: dict[str, Any], depth: int = 0) -> str:
    """Render the mapping/scalar subset accepted by control_yaml.py."""
    lines: list[str] = []
    prefix = "  " * depth
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            lines.append(_render_control_mapping(value, depth + 1).rstrip("\n"))
        else:
            text = str(value)
            if "\n" in text or "\r" in text or text.startswith(("|", ">")):
                raise ValueError(f"cannot persist unsupported control scalar for {key!r}")
            lines.append(f"{prefix}{key}: {text}")
    return "\n".join(lines) + "\n"


def _atomic_write(path: Path, text: str) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(text, encoding="utf-8")
    os.replace(temp, path)


def _minimum_lifecycle_conflicts(system: dict[str, Any]) -> tuple[dict[str, Any], list[tuple[str, str]]]:
    entries, root_problems = unknown_entries(system)
    conflicts: list[tuple[str, str]] = []
    if root_problems:
        return {}, [("unknowns", item) for item in root_problems]

    for path in MINIMUM_MATERIAL_PATHS:
        value = fact_value(system, path)
        is_unknown = canonical_token(value) == "UNKNOWN"
        has_entry = path in entries
        if has_entry and not is_unknown:
            conflicts.append(
                (path, f"unknowns.{path} exists while {path} is {value!r}, not canonical UNKNOWN")
            )
        elif is_unknown and not has_entry:
            conflicts.append((path, f"{path} is UNKNOWN but has no lifecycle entry under unknowns"))
    return dict(entries), conflicts


def _init_new_home(args: argparse.Namespace, home: Path) -> int:
    missing_settings: list[str] = []
    if args.timezone is None:
        missing_settings.append("confirmed canonical_timezone is required before ENA.yaml can be created")
    if args.language is None:
        missing_settings.append("confirmed canonical_language is required before ENA.yaml can be created")
    if missing_settings:
        return _print_not_ready("UNINITIALIZED", missing_settings)

    language_problem = language_tag_problem(args.language)
    if language_problem:
        print(f"ENA First Use: ERROR: --language: {language_problem}", file=sys.stderr)
        return 2
    try:
        load_timezone(args.timezone)
    except TimezoneUnavailable as exc:
        print(f"ENA First Use: ERROR: {exc}", file=sys.stderr)
        return 2

    command = [
        sys.executable,
        str(Path(__file__).with_name("ena_init.py")),
        "--home", str(home),
        "--timezone", args.timezone,
        "--language", args.language,
        "--host-profile", args.host_profile,
        "--system-valid-hours", str(args.system_valid_hours),
    ]

    complete_verified_minimum = bool(
        args.verified_recovery is not None
        and args.verified_rescuer is not None
        and args.rescuer_type in RESCUER_TYPES
    )
    if complete_verified_minimum:
        command += [
            "--recovery", args.verified_recovery,
            "--rescuer", args.verified_rescuer,
            "--rescuer-type", args.rescuer_type,
            "--recovery-evidence", args.recovery_evidence,
            "--rescuer-evidence", args.rescuer_evidence,
            "--verified-minimum",
        ]

    result = subprocess.run(command, text=True, capture_output=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        message = (result.stderr or result.stdout).strip()
        print(f"ENA First Use: ERROR: {message}", file=sys.stderr)
        return 2

    if complete_verified_minimum:
        problems = preflight_problems(home)
        if problems:
            return _print_not_ready("INITIALIZED_NOT_READY", problems)
        return _print_ready()

    # Partial verification is applied only after a truthful NOT_READY home exists.
    if args.verified_recovery is not None or args.verified_rescuer is not None:
        return _update_existing(args, home)

    problems = preflight_problems(home)
    if problems:
        return _print_not_ready("INITIALIZED_NOT_READY", problems)
    return _print_ready()


def _update_existing(args: argparse.Namespace, home: Path) -> int:
    config_path = home / "ENA.yaml"
    system_path = home / "SYSTEM.yaml"
    if not (config_path.is_file() and system_path.is_file()):
        print(
            "ENA First Use: ERROR: inconsistent home: ENA.yaml and SYSTEM.yaml must either both exist or both be absent",
            file=sys.stderr,
        )
        return 2

    try:
        tz, configured_timezone = require_initialized_home(home)
        config = read_control(config_path)
        system = read_control(system_path)
    except EnaHomeError as exc:
        print(f"ENA First Use: ERROR: {exc}", file=sys.stderr)
        return 2

    configured_language = scalar(config, "canonical_language")
    language_problem = language_tag_problem(configured_language)
    if language_problem:
        print(f"ENA First Use: ERROR: ENA.yaml canonical_language: {language_problem}", file=sys.stderr)
        return 2

    if args.timezone is not None and args.timezone != configured_timezone:
        print(
            f"ENA First Use: ERROR: --timezone {args.timezone!r} conflicts with confirmed canonical_timezone "
            f"{configured_timezone!r}; reconcile the stable setting explicitly instead of overwriting it here",
            file=sys.stderr,
        )
        return 2
    if args.language is not None:
        problem = language_tag_problem(args.language)
        if problem:
            print(f"ENA First Use: ERROR: --language: {problem}", file=sys.stderr)
            return 2
        if args.language != configured_language:
            print(
                f"ENA First Use: ERROR: --language {args.language!r} conflicts with confirmed canonical_language "
                f"{configured_language!r}; reconcile the stable setting explicitly instead of overwriting it here",
                file=sys.stderr,
            )
            return 2

    # Inspection is observational. Merely reading an existing scalar is never
    # permission to promote it, normalize minimum_ready, refresh timestamps, or
    # delete lifecycle evidence.
    updating_recovery = args.verified_recovery is not None
    updating_rescuer = args.verified_rescuer is not None
    if not updating_recovery and not updating_rescuer:
        problems = preflight_problems(home)
        if problems:
            return _print_not_ready("INITIALIZED_NOT_READY", problems)
        return _print_ready()

    if not isinstance(system.get("recovery"), dict) or not isinstance(system.get("rescue"), dict):
        print("ENA First Use: ERROR: SYSTEM recovery/rescue surfaces must be mappings", file=sys.stderr)
        return 2

    entries, conflicts = _minimum_lifecycle_conflicts(system)
    targets = set()
    if updating_recovery:
        targets.add("recovery.primary")
    if updating_rescuer:
        targets.add("rescue.primary")
    unaddressed = [(path, message) for path, message in conflicts if path not in targets]
    if unaddressed:
        print("ENA First Use: ERROR: minimum lifecycle state is inconsistent; refusing to infer a repair", file=sys.stderr)
        for _, message in unaddressed:
            print(f"- {message}", file=sys.stderr)
        return 2

    working = deepcopy(system)
    recovery = working["recovery"]
    rescue = working["rescue"]
    assert isinstance(recovery, dict) and isinstance(rescue, dict)

    now = datetime.now(tz)
    valid_until = now + timedelta(hours=args.system_valid_hours)

    if updating_recovery:
        recovery["primary"] = args.verified_recovery
        recovery["verification_confidence"] = SELF_ASSERTED
        recovery["verification_evidence"] = args.recovery_evidence
        recovery["verified_at"] = now.isoformat()
        entries.pop("recovery.primary", None)

    if updating_rescuer:
        rescue["primary"] = args.verified_rescuer
        if args.rescuer_type is not None:
            rescue["type"] = args.rescuer_type
        rescue["verification_confidence"] = SELF_ASSERTED
        rescue["verification_evidence"] = args.rescuer_evidence
        rescue["verified_at"] = now.isoformat()
        entries.pop("rescue.primary", None)

    working["unknowns"] = entries if entries else "[]"

    # Recompute the snapshot bit only after an explicit evidence-bearing update.
    # A plain scalar already present on disk is never enough by itself.
    desired_ready = "true" if not minimum_fact_problems(working) else "false"
    working["minimum_ready"] = desired_ready
    working["checked_at"] = now.isoformat()
    working["valid_until"] = valid_until.isoformat()

    remaining_entries, remaining_conflicts = _minimum_lifecycle_conflicts(working)
    del remaining_entries
    if remaining_conflicts:
        print("ENA First Use: ERROR: verified update would leave an inconsistent minimum lifecycle", file=sys.stderr)
        for _, message in remaining_conflicts:
            print(f"- {message}", file=sys.stderr)
        return 2

    try:
        _atomic_write(system_path, _render_control_mapping(working))
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"ENA First Use: ERROR: cannot update SYSTEM.yaml safely: {exc}", file=sys.stderr)
        return 2

    problems = preflight_problems(home)
    if problems:
        return _print_not_ready("INITIALIZED_NOT_READY", problems)
    return _print_ready()


def main() -> int:
    p = argparse.ArgumentParser(description="Advance or inspect ENA First Use without guessing missing authority.")
    p.add_argument("--home", default="~/.ena", help="ENA state directory (default: ~/.ena)")
    p.add_argument("--timezone", help="Confirmed/pre-provisioned IANA timezone; never inferred as confirmation")
    p.add_argument("--language", help="Confirmed/pre-provisioned working-language tag")
    p.add_argument("--host-profile", choices=("resident", "session"), default="session")
    p.add_argument("--verified-recovery", help="Caller-verified external recovery path/reference")
    p.add_argument("--recovery-evidence", help="Durable reference/description of the recovery verification")
    p.add_argument("--verified-rescuer", help="Caller-verified human/Agent/Host recovery actor")
    p.add_argument("--rescuer-evidence", help="Durable reference/description of the rescuer verification")
    p.add_argument("--rescuer-type", choices=("human", "agent", "host"))
    p.add_argument("--system-valid-hours", type=int, default=168)
    args = p.parse_args()

    if args.system_valid_hours <= 0:
        print("ENA First Use: ERROR: --system-valid-hours must be > 0", file=sys.stderr)
        return 2
    try:
        args.verified_recovery = _validate_reference("--verified-recovery", args.verified_recovery)
        args.verified_rescuer = _validate_reference("--verified-rescuer", args.verified_rescuer)
    except ValueError as exc:
        print(f"ENA First Use: ERROR: {exc}", file=sys.stderr)
        return 2

    if args.verified_recovery is not None:
        problem = evidence_problem(args.recovery_evidence)
        if problem:
            print(f"ENA First Use: ERROR: --recovery-evidence {problem}", file=sys.stderr)
            return 2
    elif args.recovery_evidence is not None:
        print("ENA First Use: ERROR: --recovery-evidence requires --verified-recovery", file=sys.stderr)
        return 2

    if args.verified_rescuer is not None:
        problem = evidence_problem(args.rescuer_evidence)
        if problem:
            print(f"ENA First Use: ERROR: --rescuer-evidence {problem}", file=sys.stderr)
            return 2
    elif args.rescuer_evidence is not None:
        print("ENA First Use: ERROR: --rescuer-evidence requires --verified-rescuer", file=sys.stderr)
        return 2

    if args.rescuer_type is not None and args.verified_rescuer is None:
        print("ENA First Use: ERROR: --rescuer-type requires --verified-rescuer", file=sys.stderr)
        return 2

    home = Path(args.home).expanduser().resolve()
    config_exists = (home / "ENA.yaml").exists()
    system_exists = (home / "SYSTEM.yaml").exists()
    if config_exists != system_exists:
        print(
            "ENA First Use: ERROR: inconsistent home: ENA.yaml and SYSTEM.yaml must either both exist or both be absent",
            file=sys.stderr,
        )
        return 2
    if not config_exists:
        return _init_new_home(args, home)
    return _update_existing(args, home)


if __name__ == "__main__":
    raise SystemExit(main())
