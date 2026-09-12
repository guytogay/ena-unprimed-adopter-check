# Reference tools

These scripts use only the Python standard library. An Agent can run them as examples and replace them with stronger Host-native mechanisms later.

Run repository-relative examples from the ENA release/checkout root unless a command uses only absolute paths. If an evaluation must keep the delivered snapshot byte-clean, use `python -B ...` or run from a disposable copy so Python does not create `__pycache__` next to the shipped tools.

```text
ena_init.py                 create ENA.yaml, SYSTEM.yaml and working directories
ena_first_use.py            honestly advance/inspect First Use without guessing authority
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

Shared modules are part of the reference implementation too: `control_yaml.py` is the strict mapping/scalar reader; `ena_home.py` resolves initialized-home and canonical-clock boundaries; `ena_text.py` handles ENA-owned UTF-8 text; `jsonl_source.py` validates declared JSONL inputs; `timezone_utils.py` resolves the canonical clock; `language_tag.py` validates the bounded language-tag syntax; and `minimum_readiness.py` is the single readiness predicate shared by First Use and preflight.

`control_yaml.py` intentionally supports only ENA's mapping/scalar control subset and fails closed on unsupported YAML features such as block sequences and multiline scalars. A document example intended to be copied into a control file must stay inside that subset.

`timezone_utils.py` keeps UTC usable without an external timezone database and gives an actionable error when another IANA timezone is unavailable. The shipped sentinel `REPLACE_WITH_CONFIRMED_IANA_TIMEZONE` is diagnosed as an unfilled example placeholder rather than being misreported as missing `tzdata`.

## Readiness interaction

`ena_preflight.py` answers whether ordinary ENA-active work may rely on the First Use minimum. It is **not** a universal permission gate in front of every helper: blanket-blocking setup/repair tools would make bootstrap and recovery circular.

| surface | NOT_READY expectation | mechanical behavior |
| --- | --- | --- |
| `ena_first_use.py` | intended to run | reports/advances First Use; with no evidence-bearing update on an existing home it is observational and does not rewrite state |
| `ena_preflight.py` | intended to run | returns `REFRESH REQUIRED` / exit `2` until the shared minimum predicate passes |
| `system_unknowns.py`, `fact_authority.py`, `ena_actor.py` | intended to run | inspection/reporting; success does **not** imply the home is READY |
| `change_scaffold.py`, `safe_change_state.py`, `validate_change.py` | may run when their own prerequisites are satisfied | these support repair/validation; their own state/input gates still apply |
| candidate/evolution helpers | may be usable after initialization | a helper exit `0` is success for that helper, not a global readiness claim |
| ordinary ENA-active capability workflows | normally require READY | callers/Hosts should run preflight even where a small reference helper does not embed a universal gate |

The durable relation is:

```text
HELPER_SUCCESS != HOME_READY
PREFLIGHT_READY = shared minimum predicate
NOT_READY != all setup/repair tools forbidden
```

## Attribution on durable artifacts

`ena_actor.py` resolves attribution for durable artifacts: who acted on this Host (`executor`), who asked (`initiated_by`), through which channel, and with which transport correlation id.

```text
executor != initiated_by != authority
supplied value = SELF_ASSERTED
nothing supplied = UNKNOWN
```

`change_scaffold.py` (package `status.yaml`), `safe_change_state.py` (every `transitions.jsonl` line), `validate_change.py` (validation events), `candidate_record.py` and `candidate_outcome.py` (candidate and decision records) carry the fixed five-field actor block.

The Host integration may supply:

```text
ENA_ACTOR_EXECUTOR
ENA_INITIATED_BY
ENA_CHANNEL
ENA_CORRELATION_ID
ENA_PEER_CALLER
ENA_PEER_TASK_ID
```

A real Host was observed filtering its own `DSH_*` namespace before a dispatched session, so `ENA_PEER_*` is the primary bridge contract. `DSH_PEER_*` is compatibility fallback only. Missing bridge values remain `UNKNOWN`; attribution is not authorization.

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
python tools/test_language_tag.py
python tools/test_first_use.py
python tools/test_doc_control_yaml.py
python tools/self_test.py
```

Expected final output from `self_test.py`:

```text
ENA reference tools: OK
```

The repository CI runs the reference checks on Linux and Windows.

## Initialize and advance First Use

The executable cold-adoption surface is:

```text
python tools/ena_first_use.py --home ~/.ena
```

Without confirmed timezone/language it returns NOT_READY and does not create an initialized home. With confirmed shared settings but no verified recovery/rescuer it creates an honest NOT_READY home with material UNKNOWN lifecycle entries.

`ena_init.py` remains a lower-level initializer:

```text
python tools/ena_init.py \
  --home ~/.ena \
  --timezone CONFIRMED_IANA_TIMEZONE \
  --language CONFIRMED_LANGUAGE_TAG
```

This creates `SYSTEM.yaml` with `minimum_ready: false` unless the caller explicitly supplies the fully verified minimum.

For a trusted deployment/workspace policy that already performed both reality contacts:

```text
python tools/ena_init.py \
  --home ~/.ena \
  --timezone CONFIRMED_IANA_TIMEZONE \
  --language CONFIRMED_LANGUAGE_TAG \
  --host-profile session \
  --recovery VERIFIED_RECOVERY_REFERENCE \
  --recovery-evidence DURABLE_RECOVERY_CHECK_REFERENCE \
  --rescuer VERIFIED_RESCUER_REFERENCE \
  --rescuer-evidence DURABLE_RESCUER_CHECK_REFERENCE \
  --rescuer-type human \
  --verified-minimum
```

`--verified-minimum` is not automatic proof. It records `verification_confidence: SELF_ASSERTED`, the caller-supplied evidence references, and `verified_at`. ENA is recording the caller/integration's verification claim, not authenticating an arbitrary external mechanism.

For incremental adoption, `ena_first_use.py` requires evidence whenever a minimum fact is submitted as verified:

```text
python tools/ena_first_use.py --home ~/.ena \
  --verified-recovery REAL_RECOVERY_REFERENCE \
  --recovery-evidence DURABLE_RECOVERY_CHECK_REFERENCE

python tools/ena_first_use.py --home ~/.ena \
  --verified-rescuer REAL_RESCUER_REFERENCE \
  --rescuer-evidence DURABLE_RESCUER_CHECK_REFERENCE \
  --rescuer-type human
```

The short `--recovery` / `--rescuer` aliases are intentionally not accepted by `ena_first_use.py`: an existing or newly supplied scalar must not be confused with an evidence-bearing verified minimum fact.

On an existing home, a First Use call with no `--verified-*` update is observational. It does not refresh timestamps, normalize `minimum_ready`, promote an existing scalar, or delete lifecycle entries. A contradictory minimum lifecycle entry fails closed until the affected fact is explicitly reconciled with an evidence-bearing update.

## Inspect fact authority in an existing home

Older schema-0.2 homes may contain live recovery/runtime/communication facts in both `ENA.yaml` and `SYSTEM.yaml`. Inspect the overlap without rewriting either file:

```text
python tools/fact_authority.py --home ~/.ena
```

Stable configuration and pointers are ENA-owned; freshness-bounded live facts are SYSTEM-owned. A fresh known SYSTEM live value is current while a conflicting legacy ENA value remains visible. SYSTEM `UNKNOWN`, absent, or stale never borrows a legacy ENA live value as current truth. `canonical_timezone` remains ENA-owned; a conflicting known legacy SYSTEM duplicate makes clock-dependent reference tools fail closed until reconciled.

## Preflight at session/startup time

```bash
python tools/ena_preflight.py --home ~/.ena
```

Exit `0` means the shared First Use minimum currently passes. Exit `2` means refresh/reconciliation is required. The gate re-checks both minimum facts and their verification provenance; a forged `minimum_ready: true` bit is not proof. Only canonical lowercase `true` is accepted.

## Validate material UNKNOWN lifecycle

```text
python tools/system_unknowns.py --home ~/.ena
```

This check is read-only. It validates lifecycle metadata for facts registered as material in `SYSTEM.yaml`; it does not guess that every bare `UNKNOWN` matters and it does not create a second history ledger. The fact itself remains `UNKNOWN`; `STALLED_UNKNOWN` is lifecycle metadata only.

Preflight checks contradictions involving the fixed minimum (`recovery.primary`, `rescue.primary`) because those facts participate directly in READY. It does not embed the entire UNKNOWN lifecycle checker: an unrelated material UNKNOWN does not automatically become a startup blocker.

## Create and arm a safe-change package

Choose the Host profile from `SAFE-CHANGE.md`:

```text
python tools/change_scaffold.py --home ~/.ena --name fix-config --profile session
```

or use `--profile resident` for a long-running service/daemon style Agent.

The scaffold requires an initialized ENA home and stamps the package with that home's confirmed `canonical_timezone`. A refused scaffold leaves no package behind. It creates machine-readable `status.yaml` / `rescue.yaml`, a `change.md`, backup directory, and an intentionally non-working `rollback.py` placeholder. Replace the placeholder or record a verified Host-native recovery action before arming.

After filling the real recovery facts:

```text
python tools/safe_change_state.py CHANGE_PACKAGE armed
python tools/safe_change_state.py CHANGE_PACKAGE applied
python tools/safe_change_state.py CHANGE_PACKAGE retained --evidence VALIDATION_EVENT_OR_RESULT_REF
```

The gate requires evidence for `retained`, `restored`, and `failed`. `automatic_rollback` accepts exactly `true` or `false`; typos such as `flase`, `maybe`, or `yes` block rather than being interpreted as manual recovery.

| `rescue.yaml` | meaning | package-local `rollback.py` |
| --- | --- | --- |
| `automatic_rollback: false` | manual or Host-triggered recovery | placeholder/absent is fine |
| `automatic_rollback: true` + `automatic_rollback_reference: <timer/scheduler/supervisor>` | a real Host-native automatic rollback | not required |
| `automatic_rollback: true` without a reference | blocked | — |
| `automatic_rollback: false` with a reference | blocked as contradictory | — |
| `automatic_rollback` unresolved | only a configured package-local script may arm | required |

`rollback_artifact: configured_script` means the artifact is readable and no longer the placeholder; it does **not** prove the script executes successfully or restores operation. The armed CLI prints this proof boundary. Host/caller rollback implementations are responsible for refusing destructive rollback after terminal states; `safe_change_state.py` cannot intercept an arbitrary external recovery command.

For a directly usable session/coding example based on Git branch + worktree + revert, see `examples/change/SESSION-GIT-WORKTREE.md`.

## Validate immediately after a bounded change

```bash
python tools/validate_change.py \
  --home ~/.ena \
  --name python-compile \
  --target tools/example.py \
  -- python -m py_compile tools/example.py
```

The wrapper preserves the check command's exit status and appends a validation event inside the selected initialized ENA home. If `ENA.yaml` is absent, it fails instead of silently creating a new home. Use `--repair-of PRIOR_VALIDATION_EVENT_ID` to link a repair to a failed event. Raw stdout/stderr is not persisted unless `--include-output` is explicitly used.

## Report stale knowledge/capability records

```bash
python tools/freshness_scan.py \
  --input examples/evolution/FRESHNESS.example.jsonl \
  --output freshness-report.json
```

Records without an explicit freshness policy are reported as `unknown`. Declared but unreadable timestamps remain visible as invalid metadata instead of falling back silently. `--fail-on-stale` uses semantic exit `3`; `--fail-on-unparseable` uses semantic exit `4`. These tool-specific result codes are intentional and are not generic refusal codes.

## Prepare Sleep / Dream material

```bash
python tools/sleep_prepare.py \
  --experience examples/evolution/EXPERIENCE.example.jsonl \
  --memory examples/evolution/MEMORY.example.jsonl \
  --output sleep-input.json
```

The bundle records input references, SHA-256 digests, source/selected counts and bounded selection policy. The reference `tail` policy is only a conservative transport example, not the complete retrieval semantics in `SLEEP-DREAM.md`.

Combine authorized sources before sampling when needed:

```bash
python tools/combine_dream_material.py \
  --memory examples/evolution/MEMORY.example.jsonl \
  --knowledge examples/evolution/KNOWLEDGE.example.jsonl \
  --capabilities examples/evolution/CAPABILITIES.example.jsonl \
  --output dream-material.jsonl

python tools/dream_sample.py \
  --memory dream-material.jsonl \
  --output dream-set.json \
  --seed 42
```

The sampler records its effective seed and exact input reference/digest so the sampling decision can be replayed. Advertised/catalog capabilities remain distinct from installed/verified abilities.

## Record a speculative candidate

```text
python tools/candidate_record.py \
  --home ~/.ena \
  --origin dream \
  --candidate "IDEA" \
  --reality-check "CHECK"
```

The helper resolves the selected initialized home's `evolution.speculative_candidates` pointer (default `evolution/candidates/speculative/`) and writes there. It does **not** always write to the default `~/.ena`; omitting `--home` simply selects that default, which must itself be initialized. New records use `truth_status: speculative` and remain separate from factual memory until reality contact produces evidence.
