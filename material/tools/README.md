# Reference tools

These scripts use only the Python standard library. An Agent can run them as examples and replace them with stronger Host-native mechanisms later.

```text
ena_init.py                 create ENA.yaml, SYSTEM.yaml and working directories
ena_preflight.py            fail fast when First Use is missing/not ready/stale
system_unknowns.py          validate lifecycle metadata for material SYSTEM UNKNOWNs
fact_authority.py           report stable/live fact authority in existing schema-0.2 homes
ena_actor.py                resolve who executed an action and who initiated it
change_scaffold.py          create a timestamped safe-change package skeleton
safe_change_state.py        gate SAFE-CHANGE state transitions and evidence
validate_change.py          run one deterministic check and record PASS/FAIL experience
freshness_scan.py           report fresh/stale/unknown JSONL records from explicit metadata
sleep_prepare.py            build a bounded Sleep input bundle from JSONL records
combine_dream_material.py   combine memory + knowledge + capability material
dream_sample.py             sample a Dream set with biased randomness / distance
candidate_record.py         write new candidates only into the speculative path
candidate_outcome.py        persist an already-made reality-contact outcome
self_test.py                verify the reference tools against included sample data
```

`control_yaml.py` is a shared strict reader used by the control-file tools. It intentionally supports only ENA's mapping/scalar control subset and fails closed on unsupported YAML features such as sequences and multiline scalars.

`ena_home.py` is the shared boundary for "is this an initialized ENA home, and which clock does it record?". It refuses a home without a readable `ENA.yaml` and a resolvable `canonical_timezone`, and it resolves the home that owns a SAFE-CHANGE package. Tools that maintain durable ENA state call it instead of growing their own copy, so a fix to the boundary cannot miss a sibling tool.

`ena_text.py` reads ENA-owned text files tolerating a leading UTF-8 byte order mark, because some Host-native write paths add one (PowerShell 5.1 `Out-File -Encoding UTF8`, `Set-Content -Encoding UTF8`, `Export-Csv`). A BOM carries no content, so accepting it cannot change what a declared file means.

`jsonl_source.py` is the shared reader for declared JSONL inputs used by Sleep/Dream/freshness tools. A path that was explicitly supplied but is missing, unreadable, or malformed fails closed with an actionable error instead of silently becoming an empty source.

`timezone_utils.py` keeps UTC usable without an external timezone database and gives an actionable error when another IANA timezone is unavailable. Some Windows Python installations need the optional `tzdata` package before zones such as `Asia/Shanghai` can be resolved.

`ena_actor.py` resolves attribution for durable artifacts: who acted on this Host (`executor`), who asked (`initiated_by`), through which channel, and with which transport correlation id. It exists because a Host can be worked on by a local conversation, by a scheduled job, and by another Agent that reached it over A2A — and without attribution a later reader cannot tell those apart. Three distinctions are deliberate:

```text
executor != initiated_by != authority     (this module never records authority)
supplied value = SELF_ASSERTED            (never claim a verified identity)
nothing supplied = UNKNOWN                (never default to "local agent")
```

## Attribution on durable artifacts

`change_scaffold.py` (package `status.yaml`), `safe_change_state.py` (every `transitions.jsonl` line), `validate_change.py` (validation events), `candidate_record.py` and `candidate_outcome.py` (candidate and decision records) all record an `actor` block:

```json
"actor": {
  "executor": "lxc-dsh/session-3d75c2ad",
  "initiated_by": "peer:pc-dsh",
  "channel": "a2a",
  "correlation_id": "f86dd28e-d931-42f2-861f-e25efe66f773",
  "attribution_confidence": "SELF_ASSERTED"
}
```

The Host integration supplies it through the environment; `python tools/ena_actor.py` prints what would currently be resolved.

```text
ENA_ACTOR_EXECUTOR      who is acting here
ENA_INITIATED_BY        who asked (e.g. owner, peer:pc-dsh)
ENA_CHANNEL             chat | cli | cron | a2a | api
ENA_CORRELATION_ID      Host/transport correlation id
ENA_PEER_CALLER         set by a local peer bridge that dispatches this session
ENA_PEER_TASK_ID        set by a local peer bridge that dispatches this session
```

Use a namespace the Host runtime does not itself manage: on one real Host the first
attempt used `DSH_PEER_*` and both values were **silently filtered** before reaching the
dispatched session, so the artifact recorded `channel: a2a` with `initiated_by: UNKNOWN`
and no error was raised. `DSH_PEER_CALLER` / `DSH_PEER_TASK_ID` are accepted as a
fallback, not as the primary contract.

If a peer bridge dispatches a headless session **without** passing the caller and task id, the dispatched session cannot know who asked and will honestly record `UNKNOWN` — the chain breaks at dispatch, not in the artifact. `candidate_outcome.py` keeps its operator-supplied `decided_by` next to the resolved `actor` block: the decision-maker and the initiator are different facts.

## Verify the tools

```bash
python tools/test_control_yaml.py
python tools/test_timezone_utils.py
python tools/test_jsonl_source.py
python tools/test_input_boundaries.py
python tools/test_candidate_record.py
python tools/test_candidate_outcome.py
python tools/test_fact_authority.py
python tools/test_ena_home.py
python tools/test_path_authority.py
python tools/test_safe_change_gate.py
python tools/test_freshness_scan.py
python tools/test_home_boundary_matrix.py
python tools/test_output_write_boundary.py
python tools/test_actor_attribution.py
python tools/test_system_unknowns.py
python tools/self_test.py
```

Expected final output:

```text
ENA reference tools: OK
```

The repository CI runs these checks on both Linux and Windows.

## Initialize interactively or from policy

When values are being confirmed during First Use:

```text
python tools/ena_init.py --timezone CONFIRMED_IANA_TIMEZONE --language CONFIRMED_LANGUAGE_TAG
```

This creates `SYSTEM.yaml` with `minimum_ready: false`. Verify a real recovery path and rescuer before marking it ready.

If the Host lacks timezone data for the confirmed IANA zone, the tool stops with a direct instruction to install `tzdata` or provide another confirmed zone available to that Host. It does not silently substitute a different timezone.

For a trusted deployment/workspace policy that already verified the minimum, the same tool can initialize non-interactively:

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

`--verified-minimum` is not automatic proof. The caller is asserting that the supplied recovery path and rescuer were actually verified. Missing policy values should remain unresolved rather than being filled with product defaults.

## Inspect fact authority in an existing home

Older schema-0.2 homes may contain live recovery/runtime/communication facts in both `ENA.yaml` and `SYSTEM.yaml`. Inspect the overlap without rewriting either file:

```text
python tools/fact_authority.py --home ~/.ena
```

The report follows the First Use authority split: stable configuration and pointers are ENA-owned; freshness-bounded live facts are SYSTEM-owned. A fresh known SYSTEM live value is current while a conflicting legacy ENA value remains visible. SYSTEM `UNKNOWN`, absent, or stale never borrows a legacy ENA live value as current truth. `canonical_timezone` remains ENA-owned; a conflicting known legacy SYSTEM duplicate makes clock-dependent reference tools fail closed until reconciled.

## Preflight at session/startup time

```bash
python tools/ena_preflight.py
```

Configure the Host to run this before ordinary Agent work when a startup/session hook exists. Exit code `2` means First Use must be completed/refreshed before continuing.

## Validate material UNKNOWN lifecycle

```text
python tools/system_unknowns.py --home ~/.ena
```

This check is read-only. It validates lifecycle metadata for facts already registered as material in `SYSTEM.yaml`; it does not guess that every bare `UNKNOWN` matters and it does not create a second history ledger. The fact itself remains `UNKNOWN`; `STALLED_UNKNOWN` is lifecycle metadata only. A valid stalled material fact does not automatically block unrelated startup work. See `FIRST-USE.md` for the contract and materiality boundary.

## Create and arm a safe-change package

Choose the Host profile from `SAFE-CHANGE.md`:

```text
python tools/change_scaffold.py --name fix-config --profile session
```

or use `--profile resident` for a long-running service/daemon style Agent.

The scaffold requires an initialized ENA home and stamps the package with that home's confirmed `canonical_timezone`. `--timezone` is optional and must match the home's value when given, so a package directory can no longer be named after one timezone while the home records another. A refused scaffold leaves no package behind.

The scaffold does not edit live state. It creates flat machine-readable `status.yaml` / `rescue.yaml`, a `change.md`, backup directory, and an intentionally non-working `rollback.py` placeholder. Replace the placeholder or record a verified Host-native recovery action before arming.

After filling the real recovery facts, use the state gate:

```text
python tools/safe_change_state.py CHANGE_PACKAGE armed
python tools/safe_change_state.py CHANGE_PACKAGE applied
```

A blocked `armed` transition returns exit code `2`; do not apply the live change. After the final real check:

```text
python tools/safe_change_state.py CHANGE_PACKAGE retained --evidence VALIDATION_EVENT_OR_RESULT_REF
```

The gate requires an initialized ENA home (the package must live under `<ENA home>/changes/`), records transitions on the home's confirmed timezone, requires evidence for `retained`, `restored`, and `failed`, and writes transition history to `transitions.jsonl`.

When the package cannot show a configured rollback artifact — `rollback.py` is still the scaffolded placeholder, is missing, or cannot be read — the gate requires the recovery declaration to be explicit. `automatic_rollback` accepts exactly `true` or `false`; any other scalar (`flase`, `maybe`, `yes`) blocks instead of being read as "not true, therefore manual".

| `rescue.yaml` | meaning | package-local `rollback.py` |
| --- | --- | --- |
| `automatic_rollback: false` | manual or Host-triggered recovery | placeholder/absent is fine |
| `automatic_rollback: true` + `automatic_rollback_reference: <timer/scheduler/supervisor>` | a real Host-native automatic rollback | not required |
| `automatic_rollback: true` without a reference | blocked | — |
| `automatic_rollback: false` with a reference | blocked as contradictory | — |
| `automatic_rollback` unresolved | only a configured package-local script may arm | required |

The armed transition records two orthogonal facts instead of one claim: `rollback_mode` (`not_declared`, `declared_manual_or_host_triggered`, `declared_automatic`) and `rollback_artifact` (`configured_script`, `placeholder`, `absent`, `unreadable`); a declared automatic rollback also records `automatic_rollback_reference`. `configured_script` means the artifact is readable and is no longer the placeholder — it does **not** mean the script runs, succeeds, or restores anything. Actual recovery usability still requires Host/external verification evidence.

This is reference enforcement, not magical interception. A Host must actually route state transitions through this tool (or an equivalent native hook/permission boundary) for the gate to prevent bypass.

For a directly usable session/coding example based on Git branch + worktree + revert, see:

```text
examples/change/SESSION-GIT-WORKTREE.md
```

## Validate immediately after a bounded change

Use a deterministic check the Host already trusts. For example:

```bash
python tools/validate_change.py \
  --name python-compile \
  --target tools/example.py \
  -- python -m py_compile tools/example.py
```

The wrapper returns the check command's exit status and appends a compact event to:

```text
~/.ena/evolution/experience/validation-events.jsonl
```

`validate_change.py` records into an already initialized ENA home. If `ENA.yaml` is absent, it fails instead of silently creating a new `~/.ena/` tree; initialization belongs to First Use / `ena_init.py`.

If a repair follows a failed validation, link the next run with:

```text
--repair-of PRIOR_VALIDATION_EVENT_ID
```

This is intended for PostToolUse, Git, IDE, CI or equivalent Host hooks as well as manual checks. Do not pass secrets on the command line merely to make the record self-contained. Raw stdout/stderr is not persisted unless `--include-output` is explicitly used.

## Report stale knowledge/capability records

When JSONL records carry `checked_at` and `valid_until`, scan them without inventing a product-wide TTL:

```bash
python tools/freshness_scan.py \
  --input examples/evolution/FRESHNESS.example.jsonl \
  --output freshness-report.json
```

Records without an explicit freshness policy are reported as `unknown` with reason `no_explicit_freshness_policy`. A caller may supply `--max-age-hours` as local policy when `checked_at` exists but `valid_until` does not. Use `--fail-on-stale` only when the surrounding workflow really should stop on stale records.

A record that *declares* `checked_at` or `valid_until` with a value that cannot be read is a different fact: it is reported as `unknown` with reason `unparseable_valid_until` or `unparseable_checked_at`, listed under `invalid_timestamps`, and it does not silently fall back to `--max-age-hours`. Without `--fail-on-unparseable` it does not gate; with it, the scan exits `4` so a typo cannot quietly disable a staleness check. Exit codes: `2` unusable input, `3` stale records, `4` unreadable declared metadata.

## Prepare a Sleep input bundle

```bash
python tools/sleep_prepare.py \
  --experience examples/evolution/EXPERIENCE.example.jsonl \
  --memory examples/evolution/MEMORY.example.jsonl \
  --output sleep-input.json
```

The bundle records when it was prepared plus, for each input source, its reference, SHA-256 digest, total source record count, selected record count, and the bounded tail-selection policy. This lets a later Agent tell which exact source state a Sleep run was based on even if the source files have since changed.

The reference tool's `tail` selection is only a conservative bounded transport example for recent records. It is **not** the full Sleep retrieval policy described in `SLEEP-DREAM.md`: a real Host should also retrieve or preselect older memory/knowledge when it is needed to resolve duplication, contradiction, staleness, boundaries, reusable procedures, or missing links. Do not infer “Sleep = summarize the last N records.”

Validation/repair events are also useful Sleep material. `examples/evolution/VALIDATION-TRAJECTORY.example.jsonl` shows the minimal shape.

## Combine Dream material from multiple sources

`dream_sample.py` accepts one JSONL stream. Use the combiner when the Dream should include authorized knowledge-base material and the Agent's capability surface as well as memory/session history:

```bash
python tools/combine_dream_material.py \
  --memory examples/evolution/MEMORY.example.jsonl \
  --knowledge examples/evolution/KNOWLEDGE.example.jsonl \
  --capabilities examples/evolution/CAPABILITIES.example.jsonl \
  --output dream-material.jsonl
```

Capability records should preserve whether the capability is actually installed/verified, merely advertised by an Agent Card, or only discoverable but not enabled. Do not convert an advertised or catalog capability into a real ability merely by including it in Dream material.

## Sample a free Dream

```bash
python tools/dream_sample.py \
  --memory dream-material.jsonl \
  --output dream-set.json \
  --seed 42
```

The output records the effective seed, input reference + SHA-256 digest, and record count. If `--seed` is omitted, the sampler generates a seed and writes it into the output so the exact sampling decision can be replayed later.

In `free` mode, `anchor_id` is `null` and the internally selected starting fragment is reported as `sampled_anchor_id`. This avoids making a sampled anchor look like a user-supplied problem anchor.

## Sample a problem-guided Dream

```bash
python tools/dream_sample.py \
  --memory dream-material.jsonl \
  --output dream-set.json \
  --mode problem-guided \
  --anchor-id m4 \
  --seed 42
```

In `problem-guided` mode, `anchor_id` is the explicitly supplied anchor and `sampled_anchor_id` is `null`.

The reference sampler's counts/weights are experimental field defaults, not ENA requirements.

## Record a speculative candidate

```text
python tools/candidate_record.py --origin dream --candidate "IDEA" --reality-check "CHECK"
```

The helper always writes to `~/.ena/evolution/candidates/speculative/` and sets `truth_status: speculative`. Generated claims remain separate from factual memory until reality contact produces evidence.
