# First Use

First Use should establish a usable minimum quickly. Unknown facts may remain `UNKNOWN`; do not turn first adoption into a full-system questionnaire.

Verify what can be inspected from the Host, runtime, files, tools, APIs or documentation. Do not guess when the environment can be checked.

## Minimum First Use

Complete these five things before treating ENA as active.

### 1. Confirm shared settings

Detect the Host/local timezone when possible, then ask the user to confirm the IANA timezone ENA should use. Do not impose a product default.

Use the current user interaction as a language hint when useful, then ask the user to confirm the working language tag such as `zh-CN` or `en-US`.

Ask where ENA-owned files should live. If there is no preference, a stable user-home directory such as `~/.ena/` is suitable.

Keep commands, paths, identifiers, API fields and protocol payloads in the exact form required by their systems. Use UTF-8 for ENA-owned text unless an external interface requires otherwise.

### 2. Identify one real recovery path

Find at least one action that can recover useful operation without depending on the current Agent session remaining healthy.

Examples:

- restart through a service/process/container/VM supervisor;
- start a new coding/chat session against durable disk state;
- restore a Git revision/worktree/file backup/snapshot;
- another verified Host-native recovery action.

Record the exact mechanism, or `UNKNOWN` if none exists yet.

### 3. Identify one rescuer

A rescuer may be:

- a human who can access the Host/repository/recovery mechanism; or
- another Agent reachable through A2A and able to perform or relay recovery;
- a Host-native supervisor/recovery actor when it can perform the required action independently.

Human recovery is a valid first-class path. A2A is useful when supported, but it is not required merely to complete First Use.

### 4. Write `ENA.yaml` and `SYSTEM.yaml`

`ENA.yaml` keeps confirmed settings and stable pointers.

Minimum shape:

```yaml
ena_home: .
canonical_timezone: REPLACE_WITH_CONFIRMED_IANA_TIMEZONE
canonical_language: REPLACE_WITH_CONFIRMED_LANGUAGE_TAG
text_encoding: UTF-8
recovery:
  changes: changes
evolution:
  records: evolution
  experience_inbox: evolution/experience
  speculative_candidates: evolution/candidates/speculative
  selected_candidates: evolution/candidates/selected
```

Machine-used ENA-owned paths are relative to the active ENA home, not the process working directory. Keep writable ENA state inside that home. Older schema-0.2 homes may contain absolute pointers; maintaining tools accept them only while they still resolve inside the same active home. If a copied or moved home still declares a different `ena_home`, reconcile the stable pointers before allowing new durable writes rather than following stale paths back to the old location.

`SYSTEM.yaml` is the current system map. A not-yet-ready minimum may look like:

```yaml
checked_at: 2026-09-12T02:00:00+08:00
valid_until: 2026-09-19T02:00:00+08:00
minimum_ready: false
runtime:
  host: UNKNOWN
  agent_runtime: UNKNOWN
recovery:
  primary: UNKNOWN
rescue:
  primary: UNKNOWN
unknowns:
  recovery.primary:
    state: UNKNOWN
    reason: "No verified recovery path was supplied to First Use."
    resolution_path: "Inspect or establish one external recovery mechanism, verify it, then update recovery.primary."
    owner: "agent"
    revisit_by: "2026-09-19T02:00:00+08:00"
    last_attempt_at: "2026-09-12T02:00:00+08:00"
  rescue.primary:
    state: UNKNOWN
    reason: "No verified rescuer was supplied to First Use."
    resolution_path: "Identify a human, Agent, or Host rescuer, verify reachability, then update rescue.primary."
    owner: "agent"
    revisit_by: "2026-09-19T02:00:00+08:00"
    last_attempt_at: "2026-09-12T02:00:00+08:00"
```

The dates above are only an example. Choose a freshness window appropriate to the Host. The reference initializer starts with seven days; shorten or lengthen it when the environment changes at a different rate.

Set `minimum_ready: true` only after shared settings, one recovery path, and one rescuer are recorded. If no usable recovery path or rescuer exists, leave it false and record the gap.

#### Material UNKNOWN lifecycle

Not every `UNKNOWN` needs responsibility metadata. `runtime.host` may remain a harmless unknown while a capability is unused. An unknown becomes **material** when it affects the First Use minimum, an adopted capability, recovery, communication, or another current operational claim that the Agent is relying on. Register only those material facts under `unknowns.<fact-path>`.

The current fact value stays exactly `UNKNOWN`. Its lifecycle entry carries:

```text
state
reason
resolution_path
owner
revisit_by
last_attempt_at
```

`state` is `UNKNOWN` or `STALLED_UNKNOWN`. `STALLED_UNKNOWN` is lifecycle metadata only; never replace the fact itself with `STALLED_UNKNOWN`, because that would make an unresolved fact look known to ordinary readers.

A material UNKNOWN must record a real resolution attempt. If the attempt could not be performed, record why it was impossible and the next real path instead of pretending the fact was resolved. If `revisit_by` passes while the same fact is still `UNKNOWN` and no newer attempt has established a new revisit point, mark the lifecycle `STALLED_UNKNOWN`.

When the fact becomes known, or is positively established as another state such as `UNAVAILABLE`, `NOT_NEEDED`, `NOT_APPLICABLE`, or `DEFERRED`, remove its entry from `unknowns`; `SYSTEM.yaml` is the current snapshot, not a second history ledger. Those states are distinct and must not be used merely to avoid UNKNOWN metadata.

ENA gives control semantics only to its documented state tokens. Strings such as `unset`, `n/a`, or `TBD` are ordinary literal strings, not an ever-growing global synonym list. A field with a stricter enum should validate that enum itself; do not expand `control_yaml.missing()` into natural-language guesswork.

Validate the current lifecycle with:

```text
python tools/system_unknowns.py --home ~/.ena
```

A correctly recorded `STALLED_UNKNOWN` is a valid lifecycle state; it does not by itself turn every unrelated task into a blocker. Missing/inconsistent metadata is a contract error, and First Use minimum facts still fail preflight until a real recovery path and rescuer exist.

#### One authority per fact class

Do not keep the same live fact independently in both files.

- `ENA.yaml` owns stable configuration and pointers: ENA home, canonical timezone/language, text encoding, evolution/change paths, and configured A2A discovery references.
- `SYSTEM.yaml` owns facts that can drift and need freshness: runtime/Host state, current communication reachability, current recovery/rescuer status, mutable capability/memory/change-surface facts, `checked_at`, `valid_until`, and `minimum_ready`.
- A configured reference is not a live capability. For example, keep an Agent Card URI in `ENA.yaml`; keep whether the peer is currently reachable/verified in `SYSTEM.yaml`.
- `canonical_timezone` has one authority: `ENA.yaml`. New homes do not duplicate it into `SYSTEM.yaml`.

Older schema-0.2 homes may still contain duplicated live facts. Inspect them explicitly with:

```text
python tools/fact_authority.py --home ~/.ena
```

The report is read-only. For duplicated live facts, a fresh known `SYSTEM.yaml` value is current; `SYSTEM` `UNKNOWN`, absent, or stale never borrows an old `ENA.yaml` value as current truth. The legacy value remains visible as input that needs reconfirmation. If an old `SYSTEM.yaml` also declares a different `canonical_timezone`, clock-dependent reference tools fail closed until the duplicate is reconciled.

### 5. Make the record expire

`SYSTEM.yaml` is not timeless truth.

Run `python tools/ena_preflight.py` at session/Agent/workspace start when the Host supports a startup hook. Refresh First Use when the file is past `valid_until`.

Before an important self-change, recheck the specific mutable recovery/startup/communication facts the change depends on even if `SYSTEM.yaml` has not yet expired.

## Preset / unattended adoption

First Use does not require an interactive human when the required choices were already supplied by a trusted operator, deployment policy, workspace configuration or Host integration.

A pre-provisioned value counts as confirmed only when it came from an explicit authority/policy. Do not replace a missing value with a guessed default merely to make automation pass.

The minimum can be automated as follows:

```text
pre-provision timezone + language + ENA home
→ detect/select Host profile where practical
→ verify one external recovery path
→ verify one human / Agent / Host rescuer
→ write ENA.yaml + SYSTEM.yaml
→ set minimum_ready only after those supplied mechanisms were actually verified
→ run ena_preflight.py
```

The reference initializer supports caller-verified presets, for example:

```text
python tools/ena_init.py \
  --timezone CONFIRMED_IANA_TIMEZONE \
  --language CONFIRMED_LANGUAGE_TAG \
  --host-profile session \
  --recovery VERIFIED_RECOVERY_REFERENCE \
  --rescuer VERIFIED_RESCUER_REFERENCE \
  --rescuer-type human \
  --verified-minimum
```

`--verified-minimum` is intentionally explicit. The initializer does not prove an arbitrary recovery command or rescuer is real; the caller/integration that supplies those values is responsible for that verification.

If policy does not already provide timezone, language, ENA home, recovery or rescuer, leave the setup not ready and obtain or establish the missing value instead of inventing one.

Sleep/Dream scheduling and cost limits may also be supplied by policy. If absent, leave the jobs disabled/unconfigured until an operator or applicable Host policy chooses them.

## Expand the map only when a capability needs it

After the minimum is working, inspect additional areas as they become relevant instead of blocking adoption on a complete inventory.

### Communication / A2A

When configuring A2A, identify and verify the real two-way path, Agent Card/discovery record, transport/authentication, permissions and reachable peers. Reuse the existing A2A identity mechanism. See `A2A.md`.

If a remote peer can dispatch work that may create or change durable ENA state, also verify the action-attribution handoff from **inside the dispatched session**: the bridge should propagate `ENA_PEER_CALLER` and `ENA_PEER_TASK_ID`, and `python tools/ena_actor.py` should resolve the expected peer initiator, `a2a` channel and correlation id. This is an adopted-capability check, not part of the universal minimum First Use gate. If it is not wired yet, keep the resulting attribution `UNKNOWN` rather than inventing a local initiator or claiming cross-Agent attribution is available.

### Memory / evolution

Before enabling Sleep/Dream, identify durable memory sources, experience/history, retrieval/indexing, write/update method, reversible history/snapshot, scheduler/idle/event triggers, and excluded sensitive sources. Do not create a second ENA memory database when the Host already has a suitable memory system.

### Recovery and risky self-change

Before important self-change, identify the exact affected surface, previous working state, rollback method and external recovery actor. See `SURVIVAL.md` and `SAFE-CHANGE.md`.

Additional useful facts may include Git/version control, backups, snapshots, logs, watchdogs, deployment rollback, working directories, mounts, credentials references and startup dependencies. Record unknowns explicitly rather than inventing completeness.

## First Use is minimally complete when

- timezone, language and ENA home are confirmed or explicitly pre-provisioned by trusted policy;
- `ENA.yaml` exists;
- `SYSTEM.yaml` has `checked_at`, `valid_until` and `minimum_ready: true`;
- one real recovery path is recorded;
- one human, Agent or Host rescuer is recorded;
- unknown facts remain visible as `UNKNOWN` rather than being guessed.

Then continue with the capabilities actually needed on this Host.
