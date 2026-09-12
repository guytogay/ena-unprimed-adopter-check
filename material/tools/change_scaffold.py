#!/usr/bin/env python3
"""Create a timestamped SAFE-CHANGE package using only the standard library."""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import uuid
from datetime import datetime
from pathlib import Path

from ena_actor import actor_yaml_block, resolve_actor
from ena_home import EnaHomeError, require_initialized_home, resolve_home_path
from ena_text import EnaTextWriteError, write_text
from timezone_utils import TimezoneUnavailable, load_timezone


def clean(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-")
    return value or "change"


def package_timezone(home: Path, requested: str | None):
    """Use the home's confirmed canonical timezone; never stamp a package with a foreign clock."""
    tz, tz_name = require_initialized_home(home)
    if requested is None:
        return tz, tz_name

    try:
        requested_tz = load_timezone(requested)
    except TimezoneUnavailable as exc:
        raise EnaHomeError(str(exc)) from exc
    if requested_tz != tz:
        raise EnaHomeError(
            f"--timezone {requested} does not match this ENA home's canonical_timezone {tz_name}. "
            "Omit --timezone to use the home's confirmed timezone, or re-run FIRST-USE for the home."
        )
    return tz, tz_name


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--name", required=True)
    p.add_argument("--home", default="~/.ena")
    p.add_argument(
        "--timezone",
        help="Confirmed IANA timezone; defaults to ENA.yaml canonical_timezone and must match it when given",
    )
    p.add_argument("--profile", choices=("resident", "session"), required=True)
    args = p.parse_args()

    home = Path(args.home).expanduser().resolve()
    try:
        tz, tz_name = package_timezone(home, args.timezone)
        changes = resolve_home_path(home, "recovery.changes", default_relative="changes")
    except EnaHomeError as exc:
        print(f"ENA change scaffold: ERROR: {exc}", file=sys.stderr)
        return 2

    now = datetime.now(tz)
    stamp = now.strftime("%Y%m%dT%H%M%S%f%z")
    package = changes / f"{stamp}__{clean(args.name)}__{uuid.uuid4().hex[:8]}"

    try:
        (package / "backup").mkdir(parents=True, exist_ok=False)
        write_text(
            package / "status.yaml",
            "schema_version: '0.3'\n"
            f"host_profile: {args.profile}\n"
            "state: preparing\n"
            f"updated_at: {now.isoformat(timespec='microseconds')}\n"
            "previous_state: null\n"
            "last_evidence: null\n"
            f"timezone: {tz_name}\n"
            + actor_yaml_block(resolve_actor()),
        )
        write_text(
            package / "change.md",
            "# Change\n\n"
            f"Host profile: {args.profile}\n\n"
            "What will change:\n\n"
            "Why:\n\n"
            "Previous working state:\n\n"
            "Recovery actor/path:\n\n"
            "Rollback:\n\n"
            "Incremental deterministic checks:\n\n"
            "Validation event references:\n\n"
            "Final verification:\n",
        )
        write_text(
            package / "rescue.yaml",
            "schema_version: '0.3'\n"
            f"host_profile: {args.profile}\n"
            "target: UNKNOWN\n"
            "recovery_actor: UNKNOWN\n"
            "where_to_act: UNKNOWN\n"
            "changed: UNKNOWN\n"
            "known_good: UNKNOWN\n"
            "rollback_action: UNKNOWN\n"
            "automatic_rollback: null\n"
            "automatic_rollback_reference: null\n"
            "restart_or_new_session: UNKNOWN\n"
            "verify_operation: UNKNOWN\n"
            "verify_communication: UNKNOWN\n"
            "restore_only: UNKNOWN\n"
            "fallback: UNKNOWN\n",
        )
        write_text(
            package / "rollback.py",
            "#!/usr/bin/env python3\n"
            "raise SystemExit('UNCONFIGURED_ROLLBACK: replace this placeholder or use a verified Host-native rollback action')\n",
        )
    except (OSError, EnaTextWriteError) as exc:
        shutil.rmtree(package, ignore_errors=True)
        print(f"ENA change scaffold: ERROR: cannot create package {package}: {exc}", file=sys.stderr)
        return 2

    print(package)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
