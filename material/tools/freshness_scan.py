#!/usr/bin/env python3
"""Report fresh/stale/unknown records from JSONL sources without inventing a universal TTL."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ena_text import EnaTextWriteError, write_text
from jsonl_source import JsonlSourceError, load_jsonl_source


def parse_time(value: object) -> tuple[datetime | None, bool]:
    """Return `(timestamp, declared_but_unreadable)`."""
    if value is None or not str(value).strip():
        return None, False
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None, True
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed, False


def main() -> int:
    p = argparse.ArgumentParser(
        description="Classify JSONL records as fresh/stale/unknown from explicit freshness metadata."
    )
    p.add_argument("--input", action="append", required=True, type=Path, help="JSONL source; repeatable")
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--now", help="ISO timestamp for reproducible runs; defaults to current UTC time")
    p.add_argument(
        "--max-age-hours",
        type=float,
        help="Optional caller policy used only when checked_at exists but valid_until does not",
    )
    p.add_argument("--fail-on-stale", action="store_true")
    p.add_argument(
        "--fail-on-unparseable",
        action="store_true",
        help="Exit 4 when a record declares checked_at/valid_until that cannot be read",
    )
    args = p.parse_args()

    now, now_unreadable = parse_time(args.now) if args.now else (datetime.now(timezone.utc), False)
    if now is None or now_unreadable:
        p.error("--now must be an ISO timestamp")

    results = []
    invalid_timestamps: list[dict[str, object]] = []
    counts = {"fresh": 0, "stale": 0, "unknown": 0}

    try:
        sources = [(path, load_jsonl_source(path)) for path in args.input]
    except JsonlSourceError as exc:
        print(f"ENA freshness scan: ERROR: {exc}", file=sys.stderr)
        return 2

    for path, source in sources:
        for line_no, record in zip(source.line_numbers, source.records):
            if not isinstance(record, dict):
                print(
                    f"ENA freshness scan: ERROR: record at line {line_no} in {path} must be a JSON object",
                    file=sys.stderr,
                )
                return 2
            checked_at, checked_unreadable = parse_time(record.get("checked_at"))
            valid_until, valid_unreadable = parse_time(record.get("valid_until"))

            for field, unreadable in (("checked_at", checked_unreadable), ("valid_until", valid_unreadable)):
                if unreadable:
                    invalid_timestamps.append(
                        {
                            "source_file": str(path),
                            "line": line_no,
                            "id": record.get("id"),
                            "field": field,
                            "value": record.get(field),
                        }
                    )

            if valid_until is not None:
                freshness = "fresh" if now <= valid_until else "stale"
                reason = "explicit_valid_until"
            elif valid_unreadable:
                freshness = "unknown"
                reason = "unparseable_valid_until"
            elif checked_at is not None and args.max_age_hours is not None:
                freshness = "fresh" if now <= checked_at + timedelta(hours=args.max_age_hours) else "stale"
                reason = "caller_max_age"
            elif checked_unreadable:
                freshness = "unknown"
                reason = "unparseable_checked_at"
            else:
                freshness = "unknown"
                reason = "no_explicit_freshness_policy"

            counts[freshness] += 1
            results.append(
                {
                    "id": record.get("id"),
                    "source_file": str(path),
                    "line": line_no,
                    "source_ref": record.get("source_ref"),
                    "state": record.get("state"),
                    "checked_at": record.get("checked_at"),
                    "valid_until": record.get("valid_until"),
                    "freshness": freshness,
                    "reason": reason,
                }
            )

    report = {
        "scanned_at": now.isoformat(timespec="seconds"),
        "policy": {
            "max_age_hours": args.max_age_hours,
            "fail_on_stale": args.fail_on_stale,
            "fail_on_unparseable": args.fail_on_unparseable,
        },
        "counts": counts,
        "invalid_timestamps": invalid_timestamps,
        "records": results,
    }
    try:
        write_text(args.output, json.dumps(report, indent=2, ensure_ascii=False))
    except EnaTextWriteError as exc:
        print(f"ENA freshness scan: ERROR: {exc}", file=sys.stderr)
        return 2
    print(args.output)

    if args.fail_on_unparseable and invalid_timestamps:
        return 4
    if args.fail_on_stale and counts["stale"]:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
