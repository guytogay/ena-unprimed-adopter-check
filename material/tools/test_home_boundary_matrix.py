#!/usr/bin/env python3
"""Black-box ENA home-boundary matrix across reference tools.

This test intentionally invokes the shipped tools as subprocesses instead of importing
private implementation. It preserves the independently exercised boundary class from
Issue #38:

  A uninitialized home
  B unreadable ENA.yaml
  C unreadable SYSTEM.yaml
  D healthy initialized home

A/B/C must refuse without changing durable files. D must succeed with valid inputs.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TOOLS = REPO / "tools"
PY = sys.executable

GOOD_ENA = """schema_version: '0.2'
ena_home: .
canonical_timezone: Etc/UTC
canonical_language: en-US
text_encoding: UTF-8

recovery:
  changes: changes

evolution:
  experience_inbox: evolution/experience
  speculative_candidates: evolution/candidates/speculative
  selected_candidates: evolution/candidates/selected
"""

GOOD_SYSTEM = """schema_version: '0.2'
checked_at: 2026-01-01T00:00:00+00:00
valid_until: 2099-12-31T23:59:59+00:00
minimum_ready: 'true'
runtime:
  host_profile: session
recovery:
  primary: git-revert
  verification_confidence: SELF_ASSERTED
  verification_evidence: boundary-matrix:restore-check
  verified_at: 2026-01-01T00:00:00+00:00
rescue:
  primary: human-operator
  type: human
  verification_confidence: SELF_ASSERTED
  verification_evidence: boundary-matrix:rescuer-check
  verified_at: 2026-01-01T00:00:00+00:00
"""

CORRUPT = "this is not: [valid\n  control yaml\n"

RESCUE = """schema_version: '0.3'
host_profile: session
target: probe
recovery_actor: human-operator
where_to_act: workspace
changed: config
known_good: commit
rollback_action: git-revert
automatic_rollback: false
restart_or_new_session: new-session
verify_operation: check
"""

CANDIDATE = {
    "schema_version": "0.1",
    "id": "candidate-boundary-probe",
    "created_at": "2026-09-12T06:00:00.000000+00:00",
    "timezone": "Etc/UTC",
    "origin": "work",
    "truth_status": "speculative",
    "source_fragments": ["boundary-matrix"],
    "candidate": "probe",
    "reality_check": "probe",
    "outcome": None,
}


def run(*args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PY, *map(str, args)],
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )


def build(root: Path, state: str) -> Path:
    home = root / "home"
    home.mkdir(parents=True, exist_ok=True)
    if state == "A":
        return home
    (home / "ENA.yaml").write_text(CORRUPT if state == "B" else GOOD_ENA, encoding="utf-8")
    (home / "SYSTEM.yaml").write_text(CORRUPT if state == "C" else GOOD_SYSTEM, encoding="utf-8")
    return home


def snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def candidate_source(home: Path) -> Path:
    source = home / "evolution" / "candidates" / "speculative" / "boundary-probe.json"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(json.dumps(CANDIDATE, indent=2) + "\n", encoding="utf-8")
    return source


def assert_result(
    *, tool: str, state: str, result: subprocess.CompletedProcess[str], before: dict[str, bytes], root: Path
) -> None:
    after = snapshot(root)
    if state in {"A", "B", "C"}:
        if result.returncode == 0:
            raise AssertionError(f"{tool} accepted invalid home state {state}")
        if after != before:
            changed = sorted(set(before) | set(after))
            changed = [name for name in changed if before.get(name) != after.get(name)]
            raise AssertionError(f"{tool} changed durable files in state {state}: {changed[:5]}")
    elif result.returncode != 0:
        raise AssertionError(
            f"{tool} refused healthy home: exit={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
        )


def main() -> int:
    states = ("A", "B", "C", "D")
    with tempfile.TemporaryDirectory(prefix="ena-boundary-") as temp:
        temp_root = Path(temp)

        seed = build(temp_root / "seed", "D")
        scaffold = run(
            TOOLS / "change_scaffold.py",
            "--home",
            seed,
            "--name",
            "boundary-seed",
            "--profile",
            "session",
        )
        if scaffold.returncode != 0:
            raise AssertionError(f"cannot create SAFE-CHANGE seed: {scaffold.stderr}")
        seed_pkg = Path(scaffold.stdout.strip())
        (seed_pkg / "rescue.yaml").write_text(RESCUE, encoding="utf-8")

        tools = {
            "ena_preflight": lambda home, source: [TOOLS / "ena_preflight.py", "--home", home],
            "change_scaffold": lambda home, source: [
                TOOLS / "change_scaffold.py", "--home", home, "--name", "probe", "--profile", "session"
            ],
            "validate_change": lambda home, source: [
                TOOLS / "validate_change.py", "--home", home, "--name", "probe", "--", PY, "-c", "print('ok')"
            ],
            "candidate_record": lambda home, source: [
                TOOLS / "candidate_record.py", "--home", home, "--origin", "work",
                "--candidate", "probe", "--reality-check", "probe"
            ],
            "candidate_outcome": lambda home, source: [
                TOOLS / "candidate_outcome.py", source, "--home", home, "--outcome", "retain",
                "--evidence", "boundary-probe-evidence", "--decided-by", "boundary-matrix"
            ],
            "fact_authority": lambda home, source: [
                TOOLS / "fact_authority.py", "--home", home, "--at", "2026-09-12T06:00:00+00:00"
            ],
        }

        for tool, build_args in tools.items():
            for state in states:
                root = temp_root / f"{tool}-{state}"
                home = build(root, state)
                source = home / "evolution" / "candidates" / "speculative" / "missing.json"
                if state == "D" and tool == "candidate_outcome":
                    source = candidate_source(home)
                before = snapshot(root)
                result = run(*build_args(home, source))
                assert_result(tool=tool, state=state, result=result, before=before, root=root)

        for state in states:
            root = temp_root / f"safe_change_state-{state}"
            home = build(root, state)
            changes = home / "changes"
            changes.mkdir(parents=True, exist_ok=True)
            package = changes / seed_pkg.name
            shutil.copytree(seed_pkg, package)
            before = snapshot(root)
            result = run(TOOLS / "safe_change_state.py", package, "armed")
            assert_result(
                tool="safe_change_state", state=state, result=result, before=before, root=root
            )

    print("ENA home boundary matrix: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())