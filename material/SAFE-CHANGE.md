# Safe self-change

Use this path for a change that could stop the Agent from starting, communicating, using required tools, or repairing itself.

The invariant is simple:

> Before live change, preserve the previous working state and prepare a recovery path that survives failure of the current Agent/session.

The exact mechanism depends on the Host. Do not force a daemon-style timer/A2A design onto a session-based coding Agent.

## Choose the Host profile first

### Resident runtime

Examples: systemd service, long-running container, VM Agent, daemon or always-on worker.

Prefer:

- Host supervisor/restart outside the Agent process;
- snapshot/version/file backup;
- independent timed rollback when practical;
- a human or A2A Agent able to use the recovery package;
- external communication verification after the change.

For a consequential live mutation, a 5–10 minute independent rollback window is a useful starting mechanism when the Host supports it reliably.

### Session / coding Agent

Examples: Codex, Claude Code, terminal coding Agent, chat/tool session whose process is the current interaction.

Prefer:

- durable disk/repository state outside the current session;
- Git commit/branch/worktree/revert, file backup or another exact restore point before mutation;
- recovery instructions stored on disk;
- a new session and/or human operator as the external recovery path;
- repository/tests or human-visible communication as the post-change check.

A wall-clock rollback daemon and A2A peer are not required when the Host does not naturally provide them. Do not block safe work merely because those mechanisms are absent.

For a complete reference sequence using Git branch + worktree + one bounded commit + `git revert`, see `examples/change/SESSION-GIT-WORKTREE.md`.

## A human is a valid rescuer

The recovery actor may be:

- a human with access to the Host/repository/recovery mechanism;
- another Agent through A2A;
- a Host-native external supervisor/rollback mechanism;
- a combination of these.

If an interactive human or Agent is expected to perform recovery, give that rescuer the exact package/location and obtain acknowledgement when practical. A2A acknowledgement is not a universal prerequisite on Hosts where A2A does not exist.

## One change, one recovery package

Before changing live state, create a package such as:

```text
~/.ena/changes/
  20260912T011530+0800__fix-channel/
    change.md
    rescue.yaml
    status.yaml
    transitions.jsonl
    backup/
    rollback.py | Host-native recovery reference
```

Use the timezone confirmed in `ENA.yaml`. Store the package somewhere that survives failure of the changed component/current session.

`tools/change_scaffold.py` creates a conservative skeleton. Its generated `rollback.py` is intentionally an unconfigured placeholder that exits rather than pretending recovery exists. Replace it or record a verified Host-native rollback action before arming the change. The reference gate enforces that choice: with no configured package-local script, `rescue.yaml` must declare either `automatic_rollback: false` (manual / Host-triggered recovery) or `automatic_rollback: true` together with `automatic_rollback_reference` naming the Host-native timer, scheduler or supervisor that performs the rollback. The recorded transition separates `rollback_mode` (what was declared) from `rollback_artifact` (what the package can show), and neither one is proof that recovery has actually been exercised.

## Reference state gate

`tools/safe_change_state.py` is the reference executable gate for the state machine below. It rejects malformed control files, unresolved recovery fields and invalid transitions. It also requires an evidence reference before `retained`, `restored`, or `failed`, updates `status.yaml`, and appends transition history to `transitions.jsonl`.

The gate only accepts a package inside an initialized ENA home (`<ENA home>/changes/<package>`), and it timestamps the transition with that home's confirmed timezone. A package whose home cannot be read, or that sits outside a home, is refused instead of being recorded on a guessed clock.

Example:

```text
python tools/safe_change_state.py CHANGE_PACKAGE armed
python tools/safe_change_state.py CHANGE_PACKAGE applied
python tools/safe_change_state.py CHANGE_PACKAGE retained --evidence VALIDATION_EVENT_OR_RESULT_REF
```

The reference gate has force only when the Agent/Host actually routes state transitions through it. Direct manual edits can bypass it. A Host that needs stronger enforcement should connect this gate, or an equivalent native implementation, to tool/edit/deployment hooks or permission boundaries.

## Before the change

1. **Record the target.** List the exact files, services, packages, routes, configuration or other state that will change.
2. **Preserve the previous working state.** Use Git/worktree, a file backup, deployment revision, container image, filesystem/VM snapshot, database transaction, or another reliable Host-native mechanism.
3. **Prepare rollback.** Record the exact command/script/action that restores only this change. Verify the restore point exists.
4. **Prepare `rescue.yaml`.** Give the external recovery actor enough information to restore the target without reconstructing the incident from conversation history.
5. **Prepare the profile-specific external recovery path.**
   - resident runtime: normally arm an independent rollback timer/scheduler when available;
   - session/coding Agent: ensure the durable restore point and recovery instructions survive the session, and identify the human/new-session recovery path.
6. **Confirm the external recovery actor/path is usable.** Obtain human/Agent acknowledgement when that actor is expected to intervene interactively.
7. Move `preparing -> armed` through `tools/safe_change_state.py`. Do not apply the live change if the gate rejects the package.
8. Apply the bounded live change, then move `armed -> applied` through the same gate.

## Validate close to the change

When the Host exposes a post-write, post-tool, Git, IDE, CI or service hook, run the smallest relevant **deterministic** check as close to the change as practical instead of waiting until the whole task is finished.

Examples:

```text
source/code edit     -> syntax / type / targeted test / build check
config edit          -> parser / schema / dry-run validation
service/runtime edit -> health probe / startup check
permission edit      -> access check
memory/index edit    -> read/retrieval check
```

Use tools for properties that tools can determine. Model review can add semantic context, but it should not replace a compiler, parser, test runner, linter, health probe, or other deterministic check for the property that tool actually measures.

If an incremental check fails:

1. stop expanding the same change when practical;
2. preserve the failed validation result;
3. repair the bounded fault;
4. rerun the relevant check;
5. continue only after the check passes or an explicit, evidence-backed warning is accepted.

A local PASS does not replace the final post-change check. It shortens the lifetime of defects and makes the failure/repair path attributable to the change that caused it.

`tools/validate_change.py` is a reference wrapper that runs a Host-native command, returns its exit status, and appends a compact validation event to `~/.ena/evolution/experience/validation-events.jsonl`. A later successful check can use `--repair-of` to link back to the failed event. Host-native PostToolUse/Git/IDE hooks may call it directly or implement the same behavior themselves.

## What `rescue.yaml` needs

Keep it short and executable. The reference control file intentionally uses a small flat mapping so the gate can fail closed instead of pretending to parse arbitrary YAML. Put longer explanation in `change.md`.

Record what applies on this Host:

```text
host profile
target Agent/session/repository
where recovery must run
recovery actor
exact components changed
known-good backup/snapshot/version/commit
exact rollback action
automatic rollback reference, if one exists
restart/reload/new-session action
operation verification
communication verification when relevant
exact restore scope
fallback/escalation
```

Refer to credentials; do not embed secrets merely for convenience. See `examples/change/RESCUE.example.yaml`.

## Package state

Keep one machine-readable current state in `status.yaml`:

```text
preparing   recovery package is incomplete; live state is unchanged
armed       restore point + recovery path are ready for this Host profile
applied     live change is active; recovery remains available
retained    post-change usefulness/communication check passed; new state is kept
restoring   recovery is running
restored    previous working state is back and useful operation/communication works
failed      prepared recovery did not restore usability
cancelled   change was abandoned before live mutation
```

Use `tools/safe_change_state.py` for the reference transitions. `retained`, `restored`, and `failed` require an evidence reference. Transition history lives in `transitions.jsonl` so `status.yaml` remains a small enforceable control file.

A resident runtime with a rollback timer cancels that timer only after the post-change check succeeds. A session Agent without such a timer records `retained` only after the corresponding repository/test/human communication check succeeds.

A running process alone does not prove recovery.

## Avoid two rescuers corrupting the same state

When more than one recovery actor can act, make rollback idempotent where possible or use an atomic lock/status check so a second recovery attempt detects that restoration has already happened.

A rollback should normally refuse destructive action when state is already `retained`, `restored`, or `cancelled` unless an explicit fallback says otherwise.

## Keep the validation/repair trajectory

When a check fails and a later bounded repair makes it pass, link the later validation event to the failed event. Preserve the sequence as experience:

```text
change
→ deterministic FAIL
→ bounded repair
→ deterministic PASS
→ final useful-operation check
```

Later Sleep may consolidate repeated trajectories into a procedure, earlier retrieval cue, narrower rule or candidate improvement. Do not turn one failure into a universal rule merely because it is easy to summarize.

## Keep the package

Keep the completed package as change history. Archive it only when doing so does not remove a restore dependency still needed by the current known-good state.
