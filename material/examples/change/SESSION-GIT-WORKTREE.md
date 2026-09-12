# Session / coding Agent safe change with Git worktree

Use this reference when durable Git history plus a human or fresh Agent session can recover the current work.

## 1. Preserve the current state

Before the risky change:

- inspect the working tree;
- preserve unrelated uncommitted work deliberately;
- record the current known-good commit;
- create an isolated branch/worktree when isolation is useful;
- make the bounded change there and run the repository's relevant checks.

Do not perform destructive cleanup merely to obtain a clean tree.

## 2. Create the ENA recovery package

Use `tools/change_scaffold.py`, then replace every required `UNKNOWN` in `rescue.yaml` with the real values for this repository. The package directory carries the timezone confirmed in `ENA.yaml`.

For a Git-backed session Agent, the important fields normally describe:

```yaml
host_profile: session
target: REAL_REPOSITORY_OR_AGENT_SESSION
recovery_actor: REAL_HUMAN_OR_FRESH_AGENT_SESSION
where_to_act: REAL_REPOSITORY_PATH
changed: EXACT_CHANGE_COMMIT_OR_SCOPE
known_good: KNOWN_GOOD_COMMIT
rollback_action: EXACT_REPOSITORY_RECOVERY_ACTION
automatic_rollback: false
restart_or_new_session: HOW_TO_OPEN_A_FRESH_SESSION
verify_operation: REAL_REPOSITORY_TEST_OR_TASK
verify_communication: REAL_TWO_WAY_CHECK_OR_NOT_NEEDED
restore_only: EXACT_CHANGE_SCOPE
fallback: REAL_ESCALATION_PATH
```

`automatic_rollback: false` records that recovery is this repository action rather than a package-local rollback script. The gate requires that declaration while the scaffolded placeholder is still in place, so the package cannot look like prepared automatic recovery when none exists.

A resident Host with an external timer, scheduler or supervisor instead declares `automatic_rollback: true` together with `automatic_rollback_reference: REAL_HOST_NATIVE_MECHANISM`; a package-local `rollback.py` is then not required. A reference recorded under `automatic_rollback: false` is rejected as contradictory, and a configured package-local script may arm with the declaration left unresolved (recorded as `not_declared`).

Keep the actual Git commands appropriate to the repository in `change.md` / `rescue.yaml`. Prefer recovery that reverses only the intended change and preserves unrelated later history.

## 3. Arm before applying live state

Run:

```text
python tools/safe_change_state.py CHANGE_PACKAGE armed
```

If it exits non-zero, do not apply the live/main change.

Only after the repository's own checks and the ENA gate are ready should the bounded change be applied to the live/main branch.

Then record:

```text
python tools/safe_change_state.py CHANGE_PACKAGE applied
```

## 4. Verify and decide

Run the actual repository tests/checks, startup check if relevant, and the real task or communication check the change was meant to preserve/improve.

A clean Git operation alone does not prove usefulness.

If the change should remain:

```text
python tools/safe_change_state.py CHANGE_PACKAGE retained --evidence REAL_RESULT_REFERENCE
```

If recovery is needed, transition to `restoring`, use the prepared repository recovery action, verify useful operation, then record `restored --evidence REAL_RECOVERY_REFERENCE` or `failed --evidence REAL_FAILURE_REFERENCE`.

## 5. Clean up only after the result is settled

Remove temporary worktrees/branches according to the repository's normal policy only after the change is retained or restoration is complete.

Keep the ENA recovery package while its evidence or restore information is still useful.
