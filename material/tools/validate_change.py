#!/usr/bin/env python3
"""Run one deterministic check and record the result as evolution experience."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

from ena_actor import actor_block, resolve_actor
from ena_home import EnaHomeError, require_initialized_home, resolve_home_path


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def main() -> int:
    p = argparse.ArgumentParser(
        description="Run a deterministic post-change check and append a compact validation event."
    )
    p.add_argument("--home", type=Path, default=Path.home() / ".ena")
    p.add_argument("--name", required=True, help="Short check name, e.g. py-compile or unit-test")
    p.add_argument("--target", action="append", default=[], help="Changed file/service/component; repeatable")
    p.add_argument("--change-package", help="Safe-change package path/id when applicable")
    p.add_argument("--candidate", help="Evolution candidate id/path when applicable")
    p.add_argument("--repair-of", help="Prior failed validation event id this run is repairing")
    p.add_argument("--note", help="Short non-secret context for later Sleep")
    p.add_argument("--cwd", type=Path)
    p.add_argument("--timeout", type=int, default=120)
    p.add_argument("--include-output", action="store_true", help="Also persist truncated stdout/stderr; may contain sensitive data")
    p.add_argument("command", nargs=argparse.REMAINDER, help="Command after --")
    args = p.parse_args()

    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        p.error("provide a check command after --")

    home = args.home.expanduser().resolve()
    try:
        tz, tz_name = require_initialized_home(home)
        experience = resolve_home_path(
            home,
            "evolution.experience_inbox",
            default_relative="evolution/experience",
        )
    except EnaHomeError as exc:
        print(f"ENA validation: ERROR: {exc}", file=sys.stderr)
        return 2

    started = time.monotonic()
    stdout = ""
    stderr = ""
    return_code: int | None = None
    status = "error"

    try:
        result = subprocess.run(
            command,
            cwd=args.cwd,
            text=True,
            capture_output=True,
            timeout=max(1, args.timeout),
            check=False,
        )
        stdout = result.stdout or ""
        stderr = result.stderr or ""
        return_code = result.returncode
        status = "pass" if result.returncode == 0 else "fail"
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        status = "timeout"
        return_code = 124
    except OSError as exc:
        stderr = str(exc)
        status = "error"
        return_code = 127

    event_id = f"validation-{uuid.uuid4().hex[:12]}"
    record = {
        "id": event_id,
        "occurred_at": datetime.now(tz).isoformat(timespec="seconds"),
        "timezone": tz_name,
        "type": "validation",
        "name": args.name,
        "status": status,
        "targets": args.target,
        "command": command,
        "cwd": str(args.cwd) if args.cwd else None,
        "return_code": return_code,
        "duration_ms": round((time.monotonic() - started) * 1000),
        "change_package": args.change_package,
        "candidate": args.candidate,
        "repair_of": args.repair_of,
        "note": args.note,
        "stdout_sha256": digest(stdout),
        "stderr_sha256": digest(stderr),
        "actor": actor_block(resolve_actor()),
    }
    if args.include_output:
        record["stdout_tail"] = stdout[-4000:]
        record["stderr_tail"] = stderr[-4000:]

    experience.mkdir(parents=True, exist_ok=True)
    log = experience / "validation-events.jsonl"
    with log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    if stdout:
        sys.stdout.write(stdout)
    if stderr:
        sys.stderr.write(stderr)
    print(f"ENA validation: {status.upper()} {event_id} -> {log}", file=sys.stderr)
    return int(return_code or 0)


if __name__ == "__main__":
    raise SystemExit(main())
