# Changelog

All notable changes to the clean ENA product line are recorded here.

## 1.0.0 — 2026-09-12

First stable clean-product baseline.

### Added
- Minimal First Use with explicit system freshness, recovery, rescuer, and startup preflight.
- SAFE-CHANGE reference tooling with explicit state transitions, prepared recovery, evidence-gated terminal states, and Host-profile-aware recovery semantics.
- Incremental validation events and freshness scanning for evolution evidence.
- Experimental Sleep/Dream reference tools with bounded inputs, provenance, replayable sampling, cross-session/knowledge/capability material, and speculative candidate recording.
- Reality-contact outcome recording for `retain`, `revise`, `reject`, and `restore`, while keeping the judgment outside the recorder.
- A2A guidance that separates configured discovery references from live reachability.
- Repository hygiene checks and protected-main workflow requirements.

### Hardened
- Shared initialized-home and canonical-time boundaries across durable writers.
- Collision-safe candidate output and immutable outcome records.
- UTF-8 BOM tolerance for Host-native Windows write paths.
- Fail-closed freshness metadata parsing and explicit UNKNOWN semantics.
- One authority per fact class between `ENA.yaml` and `SYSTEM.yaml`.
- Relocation-safe ENA path pointers, including moved-home protection against writes to stale absolute paths.
- Cross-platform Ubuntu/Windows regression coverage for the shipped reference tools.

### Evidence boundary
- Real Host work has demonstrated the minimum runtime chain: First Use, recovery verification, non-trivial SAFE-CHANGE, evidence-backed outcome, and continuation in a genuinely new session.
- Sleep/Dream remains experimental. Its marginal value over ordinary model reasoning is still `UNMEASURED`; v1.0.0 does not claim otherwise.
- Reference scripts only enforce boundaries that the Host actually routes through them or equivalent Host-native controls.
