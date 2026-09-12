# Sleep / Dream Quickstart

Use this after minimum First Use is complete and the Agent has identified the memory/history sources needed for this experiment.

Current sampler sizes and weights are experimental starting parameters. Do not treat them as ENA rules.

## 1. Create the working directories

```text
~/.ena/evolution/
  experience/
  candidates/
    speculative/
    selected/
  runs/
    sleep/
    dream/
  locks/
```

Keep real long-term memory and knowledge where their Host systems already keep them.

## 2. Identify Dream material sources

Dream material may come from:

- past and current session/task history that the Host exposes;
- durable Agent memory;
- authorized knowledge bases, notes, project documentation, repositories and connected files;
- verified current tools/skills/connectors/APIs from First Use or live Host discovery;
- advertised skills/capabilities from an A2A Agent Card, when present;
- discoverable but not yet installed/enabled capabilities from a Host/plugin catalog.

Keep provenance and state. A capability that is only advertised or available to install is not yet a verified ability.

Future sessions can enter the same experience/history pool and become material for later Sleep/Dream runs.

## 3. Create `sleep-dream.yaml`

Start from `examples/evolution/SLEEP-DREAM.example.yaml` and fill in the actual memory sources, write/update method, restore path, excluded sources, run limits and scheduler references when available.

## 4. Feed useful experience

Preserve concise records for corrections, repeated success/failure, surprising outcomes, unresolved problems, useful procedures, evolution results, and useful validation/repair trajectories when the Host does not already keep equivalent durable records.

When a Host hook can run a deterministic check immediately after an edit/change, `tools/validate_change.py` can record the result into the experience stream. A linked `FAIL -> repair -> PASS` sequence is useful Sleep material.

Do not dump whole conversations or tool logs by default.

## 5. Check freshness before consolidating current claims

Knowledge, Agent Cards, connector catalogs and capability inventories can drift.

Use their authoritative refresh mechanism when available. If JSONL material carries `checked_at` / `valid_until`, `tools/freshness_scan.py` can report `fresh / stale / unknown` without inventing a universal TTL.

A stale record may still be useful as history or Dream material, but do not strengthen it as current truth until it is refreshed or re-verified.

## 6. Run Sleep once manually

```text
lock memory scope
→ collect new experience and relevant memory/knowledge
→ include useful validation/repair trajectories
→ identify stale/unknown-current material that needs refresh or weaker treatment
→ find duplication/conflict/overreach/procedures/boundaries/unresolved links
→ write a consolidation plan before changing memory
→ preserve a reversible pre-run state
→ apply only the plan
→ verify memory and provenance remain usable
→ record the run
→ unlock
```

If verification fails, restore the pre-run state. A prettier summary is not success unless later retrieval or behavior improves.

## 7. Run Dream once manually

Choose either `free` or `problem-guided` mode.

Build a small mixed set containing some grounding plus older, underused, external/unresolved or distant material and an occasional random jump. Knowledge-base material and capability/possibility records may participate. The reference sampler's exact ratios are experimental.

The included reference path can combine the sample sources first:

```text
python tools/combine_dream_material.py \
  --memory examples/evolution/MEMORY.example.jsonl \
  --knowledge examples/evolution/KNOWLEDGE.example.jsonl \
  --capabilities examples/evolution/CAPABILITIES.example.jsonl \
  --output dream-material.jsonl
```

Then deliberately delay convergence and try several operations:

```text
seek remote structural similarities
combine mechanisms from different memories/knowledge sources
invert roles, assumptions or causal direction
transfer mechanisms across domains
combine a problem with an existing or discoverable capability
change constraints in a counterfactual
follow strange connections
produce multiple variants
```

Return to normal reasoning after divergence.

Record useful outputs under `~/.ena/evolution/candidates/speculative/` with `truth_status: speculative`. `tools/candidate_record.py` provides a reference path for this.

Never write Dream-generated material directly into factual memory.

## 8. Touch reality

```text
candidate
→ normal reasoning
→ refresh/verify required knowledge/capability state
→ research / observation / real task / bounded trial
→ SAFE-CHANGE.md if critical runtime state changes
→ run the smallest relevant deterministic checks close to changed state
→ retain / revise / reject / restore
→ production application if selected but not yet live
→ record the outcome and useful validation/repair trajectory
```

A candidate that survives reality contact may be recorded under `candidates/selected/`. If the successful trial happened in a sandbox/branch/worktree/preview, selection does not mean it is already deployed; apply it to live state separately and safely. Later Sleep runs decide how verified outcomes should affect durable memory.

Preserve negative and null results.

## 9. Add scheduling only after the manual path works

Ask the user to confirm cadence and cost limits. Use the Host scheduler when available and respect per-run limits.

## 10. Reference tools

Use confirmed settings rather than copying example values. See `tools/README.md` for commands.
