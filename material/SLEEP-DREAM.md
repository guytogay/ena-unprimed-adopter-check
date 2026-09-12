# Sleep and Dream

Sleep and Dream are experimental offline evolution jobs for a long-lived Agent.

- **Sleep** consolidates accumulated experience into cleaner, better-connected durable memory.
- **Dream** recombines material that normal task retrieval would not usually place together and creates speculative candidates.
- **Reality** decides what survives. Dream output is never factual memory merely because it was generated.

Use `SLEEP-DREAM-QUICKSTART.md` for the first run.

## Experimental boundary

Fragment counts, sampling weights, distance bands and cadence in examples/reference tools are field parameters, not ENA requirements. Change them when evidence from the actual Host suggests a better setting.

Negative and null results are evidence. Do not expand Dream modes or sampling complexity merely because an additional mechanism sounds plausible.

## 1. Required inputs

Before enabling these jobs, identify:

- durable memory sources;
- experience/history sources, including earlier sessions when the Host can expose them;
- authorized knowledge sources such as project documentation, note/knowledge systems, repositories, connected files or other long-lived knowledge bases;
- how memory/knowledge is retrieved or indexed;
- how durable memory can be changed and how a mistaken change can be reversed;
- how volatile knowledge/capability records can be rechecked or refreshed;
- a scheduler/idle/event mechanism when available;
- sources that must be excluded;
- the current capability inventory when available: tools, skills, connectors/plugins, APIs and other callable mechanisms;
- discoverable capabilities that are available to install/enable but are not currently active.

Keep long-term memory and knowledge in the systems that already own them. Do not duplicate them solely for ENA.

## 2. Cross-session and cross-source scope

Sleep and Dream are not limited to the current conversation.

Past sessions, task history, conversation history, project records, knowledge-base material and future sessions may all become material when the Host or an authorized integration makes them accessible. This includes note/knowledge stores, connected document systems, code repositories and other durable sources the Agent is permitted to use.

Preserve provenance so later reasoning can distinguish direct experience from user-reported, document-derived, knowledge-base-derived, Agent-derived or inferred material.

Do not assume inaccessible sessions or knowledge can be recovered. Record that limitation instead of inventing continuity.

Future sessions naturally join the same loop: useful events enter experience/history; later Sleep consolidates them; later Dream may recombine them with much older experience and knowledge.

Full transcripts or full knowledge-base dumps are not required. Stable references, indexed records or bounded fragments are preferable when they preserve enough context.

## 3. Capture useful experience while awake

If the Host does not already preserve an equivalent durable record, keep concise experience records for things likely to matter later, such as:

- user corrections;
- repeated failures/successes;
- surprising outcomes;
- useful procedures;
- unresolved problems and important exceptions;
- lessons from another Agent;
- evolution/safe-change outcomes;
- deterministic validation failures and passes;
- repair trajectories such as `failed check -> bounded repair -> passing check`.

The repair path often contains more reusable learning signal than the final successful state alone. Preserve stable references between a failed validation and the later check that repaired it.

Do not dump full conversations or tool logs by default. Keep enough provenance to recover why an occurrence matters; avoid persisting secrets merely because a validator emitted them.

`tools/validate_change.py` provides a reference way to append compact validation events from Host hooks or manual checks.

## 4. Sleep

Sleep is memory maintenance, not a daily summary.

Read new experience plus only the older memory/knowledge needed to resolve duplication, contradiction, stale knowledge, overreach, reusable procedure, boundaries, unresolved questions or missing links.

Treat repeated validation/repair trajectories as possible procedural evidence. For example, several independent instances of the same check failing for the same structural reason and being repaired in the same way may justify a narrower reusable procedure or earlier retrieval cue. One isolated failure is not enough to manufacture a general rule.

Produce a consolidation plan before changing durable memory. Useful operations include:

```text
add
merge
link
refine
correct
strengthen
weaken
mark dormant
supersede
archive
leave unchanged
create an evolution candidate
```

Before durable writes, preserve a reversible previous state using the memory system's version/history/snapshot mechanism. If memory controls startup, communication, tool access or recovery, use `SAFE-CHANGE.md` as well.

After writing, verify that memory remains readable, changed records resolve, useful provenance/counterexamples remain reachable, and a new revision/version is recorded. Restore the previous state if verification fails.

A prettier summary is not a successful Sleep run if later retrieval/behavior is unchanged.

### Freshness and drift

Long-lived knowledge, capability inventories, Agent Cards, connector catalogs and system maps can become stale.

For volatile records, preserve an authoritative source reference plus `checked_at` / `valid_until` or another Host-native freshness signal when available.

During Sleep:

1. identify records whose explicit freshness window expired, is unknown, or was declared but cannot be read;
2. refresh them from the authoritative source when the Agent is authorized and a practical refresh path exists;
3. if refresh is not possible, keep the record but mark current validity as stale/unknown rather than strengthening it as current truth;
4. preserve the historical value when it is still useful as past experience;
5. let a changed capability/document become new experience instead of silently overwriting the fact that drift occurred.

`SYSTEM.yaml` has its own expiry/preflight path. `tools/freshness_scan.py` is a reference reporter for JSONL knowledge/capability records; it does not invent a universal TTL.

An unreadable deadline is not the same fact as an absent one. A record whose `checked_at`/`valid_until` was declared but cannot be parsed is reported with an `unparseable_*` reason and listed under `invalid_timestamps`, and it must not silently become the caller's generic max-age policy; `--fail-on-unparseable` turns that into a non-zero exit so a typo cannot quietly disable a staleness check.

## 5. Dream

Dream is a variation generator. It should defeat ordinary nearest-neighbor retrieval without becoming pure noise.

Dream does not directly write generated claims into factual memory and does not directly modify the live Agent.

### Modes

```text
free             explore without a required problem anchor
problem-guided   start from one unresolved problem, then draw most additional material from distant memory/knowledge
```

### Material pools

Eligible pools may include:

```text
recent       recent experience/memory
old          substantially older memory
underused    rarely retrieved/activated memory or knowledge
external     learned from a user, document, knowledge base, A2A peer or other outside source
unresolved   unanswered question, contradiction or failed approach
salient      surprising/high-consequence/repeatedly reinforced material
distant      non-nearest material by meaning/domain/source/time
capability   installed/enabled tools, skills, connectors, APIs or other real capabilities
possibility  discoverable capabilities that are not currently installed/enabled
random       unrestricted eligible material
```

### Capability sources

Use grounded capability information rather than Dreaming capabilities into existence.

Preferred sources are:

1. First Use / live Host capability discovery and `SYSTEM.yaml`;
2. actual tool/plugin/connector registries exposed by the Host;
3. the Agent's A2A Agent Card or equivalent discovery record, when present;
4. discoverable catalogs for capabilities that could be installed/enabled.

An Agent Card is useful material because it expresses the Agent's advertised skills/capabilities, but advertised capability must still be checked against live reality before use.

Keep capability state explicit. A discoverable but uninstalled skill/connector is a **possibility**, not a capability the Agent may silently assume it already has.

Stale or unknown-freshness material may still participate in Dream as historical/speculative input when useful, but its current validity must remain explicit. Reality contact must refresh/verify it before selection depends on it.

### Sampling

Use a small mixed set with some recent grounding plus older/underused/external-or-unresolved/distant material and an occasional random jump. Knowledge-base and capability/possibility material may participate when useful.

Choose probabilistically inside pools instead of always selecting the highest-scoring record. If vector similarity exists, derive close/middle/far bands from the local distribution rather than hard-coding a universal threshold. If vectors are unavailable, approximate distance using time, domain/project, source, tags/entities, task type and retrieval history.

Concrete proportions in examples/reference tools remain experimental defaults.

### Divergent exploration

Freeze the sampled set for a round and deliberately delay convergence. Try several operations before judging the ideas:

```text
seek remote structural similarities
combine mechanisms from different memories/knowledge sources
reverse roles, assumptions or causal direction
transfer a mechanism across domains
combine a problem with an existing or discoverable capability
change constraints in a counterfactual
follow a strange connection longer than normal retrieval would
produce multiple variants
```

Keep generated content speculative during this stage.

### Candidate output

Return to normal reasoning and keep only useful hypotheses, mechanisms, questions, procedures, experiments, alternative explanations or possible self-improvements.

Dream-generated candidates belong under:

```text
~/.ena/evolution/candidates/speculative/
```

with `origin: dream` and `truth_status: speculative`. `tools/candidate_record.py` provides a reference writer.

Do not write Dream output into factual memory. A candidate that survives reality contact may move into the selected path, while factual/adaptive memory changes happen later through evidence-backed Sleep consolidation.

## 6. Return to reality

Candidates from Sleep or Dream follow `EVOLUTION.md`:

```text
candidate
→ normal reasoning
→ refresh/verify current knowledge or capability state when relevant
→ research / observation / real task / bounded trial
→ SAFE-CHANGE.md when critical runtime state changes
→ deterministic checks as close to changed state as practical
→ retain / revise / reject / restore
→ production application if selected but not yet live
→ outcome + validation/repair trajectory become new experience
→ later Sleep consolidates what reality established
```

Do not create a separate selection system for Dream output.

## 7. Scheduling and limits

Sleep and Dream do not need human biological timing. Use user-confirmed or trusted-policy cadence/cost limits and the Host's existing scheduler when possible.

Respect explicit per-run limits for source material, generated candidates, wall-clock time and model/tool cost. Do not replay an unlimited backlog after missed runs.

## 8. Reference tools

The `tools/` directory contains conservative reference helpers for initialization, preflight, safe-change scaffolding, incremental validation recording, freshness reporting, Sleep input preparation, Dream sampling and speculative candidate recording. Replace them with stronger Host-native mechanisms when available.
