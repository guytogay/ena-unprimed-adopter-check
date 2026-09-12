# Survive failure

Keep at least one recovery path outside the failure surface of the current Agent/session.

## Choose the Host profile

### Resident runtime

Examples: service, daemon, long-running container, VM Agent or always-on worker.

Use the Host's external supervisor/restart mechanism when available. Record:

- start/stop/restart actions;
- the external component that performs them;
- whether the Agent returns after Host/process failure;
- the external communication check;
- the relevant known-good restore point;
- a human or A2A rescue path.

A useful recovery order is:

```text
probe again once
→ restart
→ verify communication
→ restore the smallest relevant known-good state if still unavailable
→ restart/reload
→ verify again
→ use human/A2A/external escalation if still unavailable
```

### Session / coding Agent

Examples: Codex, Claude Code, terminal coding Agent, IDE Agent or chat/tool session.

The current process may not be restartable by a daemon. In this profile, survivability comes from durable state that a later session or human can recover.

Record:

- repository/worktree or other durable working state;
- the last known-good commit/backup before consequential self-change;
- how a new session can reopen the same workspace/state;
- how to revert/restore the last change;
- which human can intervene when the current session is gone;
- any Host session-resume mechanism if one exists.

A useful recovery order is:

```text
current session becomes unusable
→ preserve/leave durable evidence if still possible
→ human or Host starts a new session
→ inspect the latest safe-change package / Git state
→ restore the smallest relevant known-good state
→ rerun the relevant tests/checks
→ resume work
```

Do not require an always-on watchdog merely to imitate a resident service.

## External communication check

A running process is not enough.

For a resident Agent, a successful normal two-way human or A2A exchange is sufficient evidence that a rescue channel exists.

For a session/coding Agent, a human receiving a normal reply from the new/recovered session is sufficient. Relevant repository/tests may additionally verify that the changed working state is usable.

## Human and Agent rescue are both valid

A human is a first-class recovery path. Use A2A when it exists and is useful; do not make the Agent's survival depend on an A2A network that the Host does not support.

## Restore the smallest relevant state

If failure follows a recent package from `SAFE-CHANGE.md`, use its prepared rollback before restoring unrelated state.

Otherwise use the known-good recovery mechanism recorded in `SYSTEM.yaml`, such as:

- Git revision/worktree;
- service-definition backup;
- deployment revision;
- file/volume snapshot;
- container image;
- VM snapshot;
- another verified restore point.

Prefer a smaller reliable recovery over a broad old snapshot.

## Keep recovery outside the same failure path

Where possible:

- keep resident restart/supervisor control outside the Agent process;
- keep session recovery data on durable disk/repository state outside the current conversation/process;
- keep recovery packages outside the component being changed;
- do not modify the only communication path and its only recovery path in one operation;
- keep at least one human, Agent or Host mechanism able to recover the target.

## Keep `SYSTEM.yaml` fresh

Record the recovery mechanisms currently available and the Host profile in use.

When startup, workspace location, service name, A2A endpoint, recovery storage, repository, scheduler or other recovery facts change, refresh `SYSTEM.yaml` and its `checked_at` / `valid_until` values.

Before consequential self-change, recheck the specific recovery facts that change depends on even when the overall system record is still within its freshness window.
