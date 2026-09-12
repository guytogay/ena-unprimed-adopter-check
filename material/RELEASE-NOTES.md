# ENA v1.0.0

ENA v1.0.0 is the first stable release of the clean ENA product repository.

ENA exists to preserve viable agency by adding runtime capabilities that reasoning alone does not provide: grounded self-inspection, external recovery, reversible self-change, cross-session memory maintenance, idea variation, and evidence-backed evolution. It does not replace the model's ordinary judgment with a second reasoning bureaucracy.

## What ships

- **First Use and preflight** — explicit canonical settings, freshness-bounded system state, recovery/rescuer discovery, and a startup/session gate.
- **Survival and SAFE-CHANGE** — prepared recovery, preserved known-good state, explicit transition gating, Host-profile-aware rollback semantics, and evidence-gated terminal outcomes.
- **Validation and freshness** — deterministic validation events, repair linkage, and stale/unknown/unparseable fact reporting.
- **Evolution** — speculative candidate recording, reality contact, and durable `retain` / `revise` / `reject` / `restore` outcome records without moving the decision itself into the recorder.
- **Experimental Sleep/Dream** — bounded input preparation, source provenance, replayable Dream sampling, cross-session/knowledge/capability material, and explicit speculative truth status.
- **A2A boundaries** — configured discovery references are distinct from current reachability and verified capability.
- **Portable Host state** — stable/live fact authority split between `ENA.yaml` and `SYSTEM.yaml`, relocation-safe ENA paths, canonical-time enforcement, BOM-tolerant reads, and fail-closed malformed-state handling.
- **Cross-platform reference suite** — Ubuntu and Windows CI for the shipped reference tooling and repository hygiene guards.

## Field evidence

Real Host use has demonstrated a minimum end-to-end runtime chain: First Use, recovery verification, a non-trivial SAFE-CHANGE, an evidence-backed outcome, and continuation from persisted state in a genuinely new session.

That does **not** mean every ENA capability is field-proven on every Host. Reference scripts only enforce what the Host routes through them or equivalent Host-native controls.

Sleep/Dream remains experimental. Its marginal value over ordinary model reasoning is currently **UNMEASURED**. This release ships the mechanism and evidence boundaries, not a claim that Dream already improves outcomes.

## Compatibility and migration

Existing schema-0.2 homes remain readable, but v1.0.0 makes several previously implicit boundaries explicit:

- stable configuration/pointers belong to `ENA.yaml`; freshness-bounded live facts belong to `SYSTEM.yaml`;
- new machine-owned path pointers are home-relative and relocatable;
- legacy absolute pointers are accepted only when they resolve inside the active ENA home;
- a moved/copied legacy home with stale absolute identity fails closed before durable writes rather than writing back into its old location;
- annotated UNKNOWN values remain unresolved instead of being promoted to truth;
- candidate and decision artifacts are collision-safe and use the ENA canonical timezone.

## Known boundaries

- `candidate_outcome.py` records evidence references as asserted by the operator; it does not verify arbitrary external references or judge evidence sufficiency.
- Sleep/Dream sampling parameters are experimental field parameters, not normative intelligence settings.
- Multi-process transaction isolation is not claimed for candidate outcome recording.
- Host-native recovery mechanisms remain the preferred stronger implementation when available.

Licensed under Apache License 2.0.
