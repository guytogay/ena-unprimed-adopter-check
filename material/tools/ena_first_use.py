#!/usr/bin/env python3
"""Bounded executable First Use path for cold or incremental adoption.

The tool derives state from ENA.yaml + SYSTEM.yaml. It creates no bootstrap
ledger and never persists detected-but-unconfirmed stable settings.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from control_yaml import missing, scalar
from ena_home import EnaHomeError, read_control, require_initialized_home
from language_tag import language_tag_problem
from minimum_readiness import preflight_problems
from system_unknowns import canonical_token, initial_material_unknowns, requirement_is_usable, unknown_entries
from timezone_utils import TimezoneUnavailable, load_timezone


RESCUER_TYPES = {"human", "agent", "host"}


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
    if not requirement_is_usable(value):
        raise ValueError(f"{label} must be a real caller-verified reference, not {value!r}")
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
    if args.recovery is not None:
        command += ["--recovery", args.recovery]
    if args.rescuer is not None:
        command += ["--rescuer", args.rescuer]
    if args.rescuer_type is not None:
        command += ["--rescuer-type", args.rescuer_type]

    # Only mark ready at creation when all caller-verified minimum inputs needed
    # by the initializer are present. Otherwise initialize honestly NOT_READY.
    if args.recovery is not None and args.rescuer is not None and args.rescuer_type in RESCUER_TYPES:
        command.append("--verified-minimum")

    result = subprocess.run(command, text=True, capture_output=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        message = (result.stderr or result.stdout).strip()
        print(f"ENA First Use: ERROR: {message}", file=sys.stderr)
        return 2

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

    changed = False
    recovery = system.setdefault("recovery", {})
    rescue = system.setdefault("rescue", {})
    if not isinstance(recovery, dict) or not isinstance(rescue, dict):
        print("ENA First Use: ERROR: SYSTEM recovery/rescue surfaces must be mappings", file=sys.stderr)
        return 2

    if args.recovery is not None and recovery.get("primary") != args.recovery:
        recovery["primary"] = args.recovery
        changed = True
    if args.rescuer is not None and rescue.get("primary") != args.rescuer:
        rescue["primary"] = args.rescuer
        changed = True
    if args.rescuer_type is not None and rescue.get("type") != args.rescuer_type:
        rescue["type"] = args.rescuer_type
        changed = True

    entries, root_problems = unknown_entries(system)
    if root_problems:
        print(f"ENA First Use: ERROR: {root_problems[0]}", file=sys.stderr)
        return 2
    entries = dict(entries)

    now = datetime.now(tz)
    valid_until = now + timedelta(hours=args.system_valid_hours)

    # Normalize an absent/null minimum fact to the one canonical unresolved fact
    # value. Established non-ready states (UNAVAILABLE/NOT_NEEDED/etc.) remain
    # distinct and do not receive UNKNOWN lifecycle entries.
    for section in (recovery, rescue):
        raw = section.get("primary")
        if not isinstance(raw, str) or missing(raw):
            if raw != "UNKNOWN":
                section["primary"] = "UNKNOWN"
                changed = True

    recovery_value = recovery.get("primary")
    rescuer_value = rescue.get("primary")
    if canonical_token(recovery_value if isinstance(recovery_value, str) else None) == "STALLED_UNKNOWN":
        print("ENA First Use: ERROR: recovery.primary must stay UNKNOWN; STALLED_UNKNOWN belongs in lifecycle metadata", file=sys.stderr)
        return 2
    if canonical_token(rescuer_value if isinstance(rescuer_value, str) else None) == "STALLED_UNKNOWN":
        print("ENA First Use: ERROR: rescue.primary must stay UNKNOWN; STALLED_UNKNOWN belongs in lifecycle metadata", file=sys.stderr)
        return 2

    seed_entries = initial_material_unknowns(
        recovery=(recovery_value if isinstance(recovery_value, str) else "UNKNOWN"),
        rescuer=(rescuer_value if isinstance(rescuer_value, str) else "UNKNOWN"),
        checked_at=now,
        revisit_by=valid_until,
    )
    values = {
        "recovery.primary": recovery_value,
        "rescue.primary": rescuer_value,
    }
    for path, value in values.items():
        if canonical_token(value if isinstance(value, str) else None) == "UNKNOWN":
            if path not in entries and path in seed_entries:
                entries[path] = seed_entries[path]
                changed = True
        elif path in entries:
            del entries[path]
            changed = True

    system["unknowns"] = entries if entries else "[]"

    ready_facts = requirement_is_usable(recovery_value if isinstance(recovery_value, str) else None) and requirement_is_usable(
        rescuer_value if isinstance(rescuer_value, str) else None
    )
    rescuer_type = rescue.get("type")
    should_mark_ready = bool(ready_facts and rescuer_type in RESCUER_TYPES)
    desired_ready = "true" if should_mark_ready else "false"
    if system.get("minimum_ready") != desired_ready:
        system["minimum_ready"] = desired_ready
        changed = True

    if changed:
        system["checked_at"] = now.isoformat()
        system["valid_until"] = valid_until.isoformat()
        try:
            _atomic_write(system_path, _render_control_mapping(system))
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
    p.add_argument(
        "--verified-recovery", "--recovery", dest="recovery",
        help="Caller-verified external recovery path/reference",
    )
    p.add_argument(
        "--verified-rescuer", "--rescuer", dest="rescuer",
        help="Caller-verified human/Agent/Host recovery actor",
    )
    p.add_argument("--rescuer-type", choices=("human", "agent", "host"))
    p.add_argument("--system-valid-hours", type=int, default=168)
    args = p.parse_args()

    if args.system_valid_hours <= 0:
        print("ENA First Use: ERROR: --system-valid-hours must be > 0", file=sys.stderr)
        return 2
    try:
        args.recovery = _validate_reference("--verified-recovery", args.recovery)
        args.rescuer = _validate_reference("--verified-rescuer", args.rescuer)
    except ValueError as exc:
        print(f"ENA First Use: ERROR: {exc}", file=sys.stderr)
        return 2
    if args.rescuer_type is not None and args.rescuer is None:
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
