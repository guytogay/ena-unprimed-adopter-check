#!/usr/bin/env python3
"""Validate and advance the SAFE-CHANGE state machine."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from control_yaml import missing, scalar
from ena_actor import actor_block, actor_yaml_block, resolve_actor
from ena_home import EnaHomeError, home_of_package, read_control, require_initialized_home
from ena_text import read_text


ALLOWED = {
    "preparing": {"armed", "cancelled"},
    "armed": {"applied", "cancelled"},
    "applied": {"retained", "restoring"},
    "restoring": {"restored", "failed"},
    "retained": set(),
    "restored": set(),
    "failed": set(),
    "cancelled": set(),
}

REQUIRED_FOR_ARM = (
    "host_profile",
    "target",
    "recovery_actor",
    "where_to_act",
    "changed",
    "known_good",
    "rollback_action",
    "restart_or_new_session",
    "verify_operation",
)

PLACEHOLDER_MARKER = "UNCONFIGURED_ROLLBACK"
ARMED_PROOF_NOTE = (
    "NOTE: armed means the required recovery declarations/artifact shape passed this gate; "
    "this transition does not prove that recovery executes successfully or restores operation."
)

# `rollback_mode` is what the package *declared*; `rollback_artifact` is what the
# package can actually show. They are recorded separately because neither one
# implies the other: a configured script is still not proof that recovery works,
# and a Host-native timer is real automatic recovery without any local script.
ROLLBACK_MODE_NOT_DECLARED = "not_declared"
ROLLBACK_MODE_MANUAL = "declared_manual_or_host_triggered"
ROLLBACK_MODE_AUTOMATIC = "declared_automatic"

ROLLBACK_ARTIFACT_LABELS = {
    "configured": "configured_script",
    "placeholder": "placeholder",
    "absent": "absent",
    "unreadable": "unreadable",
}

ROLLBACK_ARTIFACT_DESCRIPTIONS = {
    "placeholder": "rollback.py is still the unconfigured placeholder",
    "absent": "the package has no rollback.py",
    "unreadable": "rollback.py cannot be read",
}

ROLLBACK_CLAIM_CONFLICTS = {
    "placeholder": "rollback_action points at rollback.py, which is still the unconfigured placeholder",
    "absent": "rollback_action points at rollback.py, but the package has no rollback.py",
    "unreadable": "rollback_action points at rollback.py, which cannot be read",
}

AUTOMATIC_ROLLBACK_VALUES = {"true": True, "false": False}


def rollback_state(package: Path) -> str:
    """Report what the package can actually show right now.

    `configured` means the artifact is readable and is no longer the scaffolded
    placeholder. It does not mean the script runs, succeeds, or restores
    anything: that still requires Host/external verification evidence.
    """
    script = package / "rollback.py"
    if not script.is_file():
        return "absent"
    try:
        text = read_text(script)
    except (OSError, UnicodeError):
        return "unreadable"
    return "placeholder" if PLACEHOLDER_MARKER in text else "configured"


def rollback_declaration(rescue: dict[str, object]) -> tuple[bool | None, str | None, list[str]]:
    """Read the recovery declaration, refusing anything that is not a declaration.

    `automatic_rollback` accepts exactly `true` or `false`, or stays unresolved.
    Treating every other scalar as "not true, therefore manual" would let a typo
    such as `flase` arm a package as if manual recovery had been declared.
    """
    problems: list[str] = []
    raw = scalar(rescue, "automatic_rollback")
    reference = scalar(rescue, "automatic_rollback_reference")
    has_reference = not missing(reference)

    if missing(raw):
        declared: bool | None = None
    elif raw.strip().lower() in AUTOMATIC_ROLLBACK_VALUES:
        declared = AUTOMATIC_ROLLBACK_VALUES[raw.strip().lower()]
    else:
        declared = None
        problems.append(
            f"rescue.yaml automatic_rollback is {raw!r}, which is not a declaration: "
            "use exactly true or false, or leave it unresolved"
        )

    if declared is True and not has_reference:
        problems.append(
            "rescue.yaml automatic_rollback is true but automatic_rollback_reference is unresolved: "
            "name the Host-native timer/scheduler/supervisor that performs the rollback, "
            "or declare automatic_rollback: false"
        )
    if declared is False and has_reference:
        problems.append(
            "rescue.yaml automatic_rollback is false but automatic_rollback_reference is recorded: "
            "remove the reference or declare automatic_rollback: true"
        )
    if declared is None and has_reference and missing(raw):
        problems.append(
            "rescue.yaml records automatic_rollback_reference but automatic_rollback is not declared: "
            "declare automatic_rollback: true"
        )

    return declared, reference, problems


def rollback_problems(
    rescue: dict[str, object], artifact: str
) -> tuple[list[str], str | None, str, str | None]:
    """Require the recovery declaration to match what the package can show."""
    problems: list[str] = []
    artifact_label = ROLLBACK_ARTIFACT_LABELS[artifact]
    declared, reference, declaration_problems = rollback_declaration(rescue)
    problems.extend(declaration_problems)

    mode: str | None = None
    if declared is True:
        mode = ROLLBACK_MODE_AUTOMATIC
    elif declared is False:
        mode = ROLLBACK_MODE_MANUAL
    elif not declaration_problems and artifact == "configured":
        # A configured package-local script may arm without declaring
        # automaticity; the gate records that it was not declared instead of
        # inventing a declaration for the operator.
        mode = ROLLBACK_MODE_NOT_DECLARED
    elif not declaration_problems:
        problems.append(
            f"{ROLLBACK_ARTIFACT_DESCRIPTIONS[artifact]}: configure rollback.py, declare "
            "automatic_rollback: false for manual/Host-triggered recovery, or declare "
            "automatic_rollback: true with an automatic_rollback_reference"
        )

    rollback_action = scalar(rescue, "rollback_action") or ""
    if "rollback.py" in rollback_action and artifact in ROLLBACK_CLAIM_CONFLICTS:
        problems.append(ROLLBACK_CLAIM_CONFLICTS[artifact])

    return problems, mode, artifact_label, reference


def write_status(
    path: Path,
    state: str,
    profile: str,
    previous: str,
    evidence: str | None,
    tz,
    tz_name: str,
    actor,
) -> str:
    """Write the current state snapshot and attribute this snapshot write."""
    now = datetime.now(tz).isoformat(timespec="seconds")
    text = (
        "schema_version: '0.3'\n"
        f"host_profile: {profile}\n"
        f"state: {state}\n"
        f"updated_at: {now}\n"
        f"previous_state: {previous}\n"
        f"last_evidence: {evidence if evidence else 'null'}\n"
        f"timezone: {tz_name}\n"
        + actor_yaml_block(actor)
    )
    temp = path.with_suffix(".yaml.tmp")
    temp.write_text(text, encoding="utf-8")
    os.replace(temp, path)
    return now


def main() -> int:
    p = argparse.ArgumentParser(description="Gate one SAFE-CHANGE state transition.")
    p.add_argument("package", type=Path)
    p.add_argument("to_state", choices=tuple(ALLOWED))
    p.add_argument("--evidence", help="Required for retained/restored/failed")
    args = p.parse_args()

    package = args.package.expanduser().resolve()
    status_path = package / "status.yaml"
    rescue_path = package / "rescue.yaml"
    if not status_path.is_file() or not rescue_path.is_file():
        print("SAFE-CHANGE gate: missing status.yaml or rescue.yaml", file=sys.stderr)
        return 2

    try:
        tz, tz_name = require_initialized_home(home_of_package(package))
    except EnaHomeError as exc:
        print(f"SAFE-CHANGE gate: {exc}", file=sys.stderr)
        return 2

    try:
        status = read_control(status_path)
        rescue = read_control(rescue_path)
    except EnaHomeError as exc:
        print(f"SAFE-CHANGE gate: {exc}", file=sys.stderr)
        return 2

    current = scalar(status, "state")
    profile = scalar(status, "host_profile")
    if current not in ALLOWED:
        print(f"SAFE-CHANGE gate: invalid current state {current!r}", file=sys.stderr)
        return 2
    if args.to_state not in ALLOWED[current]:
        print(f"SAFE-CHANGE gate: transition {current} -> {args.to_state} is not allowed", file=sys.stderr)
        return 2

    problems: list[str] = []
    rollback_mode: str | None = None
    rollback_artifact: str | None = None
    rollback_reference: str | None = None
    if args.to_state == "armed":
        if profile not in {"resident", "session"}:
            problems.append("status.yaml host_profile must be resident or session")
        if scalar(rescue, "host_profile") != profile:
            problems.append("rescue.yaml host_profile must match status.yaml")
        for key in REQUIRED_FOR_ARM:
            if missing(scalar(rescue, key)):
                problems.append(f"rescue.yaml {key} is unresolved")

        recovery_problems, rollback_mode, rollback_artifact, rollback_reference = rollback_problems(
            rescue, rollback_state(package)
        )
        problems.extend(recovery_problems)

    if args.to_state in {"retained", "restored", "failed"} and not args.evidence:
        problems.append(f"{args.to_state} requires --evidence")

    if problems:
        print("SAFE-CHANGE gate: BLOCKED", file=sys.stderr)
        for item in problems:
            print(f"- {item}", file=sys.stderr)
        return 2

    actor = resolve_actor()
    now = write_status(
        status_path,
        args.to_state,
        profile or "UNKNOWN",
        current,
        args.evidence,
        tz,
        tz_name,
        actor,
    )
    transition = {
        "at": now,
        "from": current,
        "to": args.to_state,
        "evidence": args.evidence,
        "timezone": tz_name,
        "actor": actor_block(actor),
    }
    if args.to_state == "armed":
        transition["rollback_mode"] = rollback_mode
        transition["rollback_artifact"] = rollback_artifact
        if rollback_mode == ROLLBACK_MODE_AUTOMATIC:
            transition["automatic_rollback_reference"] = rollback_reference
    with (package / "transitions.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(transition) + "\n")

    print(f"SAFE-CHANGE gate: {current} -> {args.to_state}")
    if args.to_state == "armed":
        print(ARMED_PROOF_NOTE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
