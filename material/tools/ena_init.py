#!/usr/bin/env python3
"""Create a minimal ENA home using only the Python standard library."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path

from language_tag import language_tag_problem
from minimum_readiness import SELF_ASSERTED, evidence_problem
from system_unknowns import initial_material_unknowns, render_unknowns_yaml, requirement_is_usable
from timezone_utils import TimezoneUnavailable, load_timezone


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--home", default="~/.ena")
    p.add_argument("--timezone", required=True, help="Confirmed/pre-provisioned IANA timezone")
    p.add_argument("--language", required=True, help="Confirmed/pre-provisioned language tag")
    p.add_argument("--host-profile", choices=("resident", "session"), default="UNKNOWN")
    p.add_argument(
        "--recovery",
        default="UNKNOWN",
        help="Recovery path/reference; it counts toward READY only with --verified-minimum and evidence",
    )
    p.add_argument(
        "--rescuer",
        default="UNKNOWN",
        help="Human/Agent/Host rescuer reference; it counts toward READY only with --verified-minimum and evidence",
    )
    p.add_argument("--rescuer-type", choices=("human", "agent", "host", "UNKNOWN"), default="UNKNOWN")
    p.add_argument("--recovery-evidence", help="Durable reference/description of the recovery verification")
    p.add_argument("--rescuer-evidence", help="Durable reference/description of the rescuer verification")
    p.add_argument(
        "--verified-minimum",
        action="store_true",
        help="Mark minimum_ready only when both supplied minimum facts were caller-verified with evidence",
    )
    p.add_argument(
        "--system-valid-hours",
        type=int,
        default=168,
        help="Initial SYSTEM.yaml freshness window; default 168 hours (7 days)",
    )
    args = p.parse_args()

    # Validate every stable/verification setting before creating directories or
    # files. A rejected caller assertion must not leave a half-initialized home.
    if args.system_valid_hours <= 0:
        raise SystemExit("--system-valid-hours must be > 0")

    language_problem = language_tag_problem(args.language)
    if language_problem:
        raise SystemExit(f"--language: {language_problem}")

    try:
        tz = load_timezone(args.timezone)
    except TimezoneUnavailable as exc:
        raise SystemExit(str(exc)) from exc

    if not args.verified_minimum and (args.recovery_evidence is not None or args.rescuer_evidence is not None):
        raise SystemExit("--recovery-evidence/--rescuer-evidence require --verified-minimum")

    if args.verified_minimum:
        if not (
            requirement_is_usable(args.recovery)
            and requirement_is_usable(args.rescuer)
            and args.rescuer_type != "UNKNOWN"
        ):
            raise SystemExit(
                "--verified-minimum requires real --recovery and --rescuer references plus a non-UNKNOWN --rescuer-type; "
                "UNKNOWN/UNAVAILABLE/NOT_NEEDED/NOT_APPLICABLE/DEFERRED do not satisfy the minimum"
            )
        recovery_evidence_issue = evidence_problem(args.recovery_evidence)
        rescuer_evidence_issue = evidence_problem(args.rescuer_evidence)
        if recovery_evidence_issue:
            raise SystemExit(f"--recovery-evidence {recovery_evidence_issue}")
        if rescuer_evidence_issue:
            raise SystemExit(f"--rescuer-evidence {rescuer_evidence_issue}")

    home = Path(args.home).expanduser().resolve()
    for rel in (
        "changes",
        "evolution/experience",
        "evolution/candidates/speculative",
        "evolution/candidates/selected",
        "evolution/runs/sleep",
        "evolution/runs/dream",
        "evolution/locks",
    ):
        (home / rel).mkdir(parents=True, exist_ok=True)

    config = home / "ENA.yaml"
    system = home / "SYSTEM.yaml"
    for path in (config, system):
        if path.exists():
            raise SystemExit(f"Refusing to overwrite existing {path}")

    config.write_text(
        "schema_version: '0.2'\n"
        "ena_home: .\n"
        f"canonical_timezone: {args.timezone}\n"
        f"canonical_language: {args.language}\n"
        "text_encoding: UTF-8\n"
        "\ncommunication:\n"
        "  a2a:\n"
        "    agent_card: UNKNOWN\n"
        "    rescue_peers: []\n"
        "\nrecovery:\n"
        "  changes: changes\n"
        "\nevolution:\n"
        "  records: evolution\n"
        "  experience_inbox: evolution/experience\n"
        "  speculative_candidates: evolution/candidates/speculative\n"
        "  selected_candidates: evolution/candidates/selected\n",
        encoding="utf-8",
    )

    checked = datetime.now(tz)
    valid_until = checked + timedelta(hours=args.system_valid_hours)
    ready = "true" if args.verified_minimum else "false"
    unknowns = initial_material_unknowns(
        recovery=args.recovery,
        rescuer=args.rescuer,
        checked_at=checked,
        revisit_by=valid_until,
    )
    recovery_verification = ""
    rescue_verification = ""
    if args.verified_minimum:
        recovery_verification = (
            f"  verification_confidence: {SELF_ASSERTED}\n"
            f"  verification_evidence: {args.recovery_evidence}\n"
            f"  verified_at: {checked.isoformat()}\n"
        )
        rescue_verification = (
            f"  verification_confidence: {SELF_ASSERTED}\n"
            f"  verification_evidence: {args.rescuer_evidence}\n"
            f"  verified_at: {checked.isoformat()}\n"
        )

    system_text = (
        "schema_version: '0.2'\n"
        f"checked_at: {checked.isoformat()}\n"
        f"valid_until: {valid_until.isoformat()}\n"
        f"minimum_ready: {ready}\n"
        "runtime:\n"
        "  host: UNKNOWN\n"
        "  agent_runtime: UNKNOWN\n"
        f"  host_profile: {args.host_profile}\n"
        "  startup: UNKNOWN\n"
        "  restart: UNKNOWN\n"
        "  supervision: UNKNOWN\n"
        "communication:\n"
        "  human: UNKNOWN\n"
        "  a2a_reachability: UNKNOWN\n"
        "recovery:\n"
        f"  primary: {args.recovery}\n"
        + recovery_verification
        + "  backup_or_snapshot: UNKNOWN\n"
        "  scheduler_or_timer: UNKNOWN\n"
        "rescue:\n"
        f"  primary: {args.rescuer}\n"
        f"  type: {args.rescuer_type}\n"
        + rescue_verification
        + "memory:\n"
        "  sources: []\n"
        "  durable_store: UNKNOWN\n"
        "  retrieval_or_index: UNKNOWN\n"
        "  write_method: UNKNOWN\n"
        "change_surfaces: []\n"
        + render_unknowns_yaml(unknowns)
    )
    system.write_text(system_text, encoding="utf-8")

    print(config)
    print(system)
    if args.verified_minimum:
        print("Minimum First Use recorded from caller-verified values with durable evidence references.")
    else:
        print("First Use is not complete yet: verify recovery/rescue facts and use the First Use evidence path.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
