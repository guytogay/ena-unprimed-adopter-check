#!/usr/bin/env python3
"""Shared attribution: who executed an action, and who initiated it.

ENA writes durable artifacts (change packages, candidates, decisions, validation
events). Without attribution a later reader cannot tell whether a change came from
the local conversation, from a scheduled job, or from another Agent that reached
this Host over A2A and had a headless session dispatched for it.

Discipline — keep these apart:

- `executor` (who acted on this Host) != `initiated_by` (who asked) != authority
  (who authorized the effect). This module never records authority.
- A value taken from the environment is `SELF_ASSERTED`, not verified. Claiming a
  verified identity would need a Host-attested source, which the reference tools
  do not have.
- When nothing is supplied the answer is `UNKNOWN`. Never default to "local agent":
  an unrecorded initiator is exactly the case that has to stay visible.
- Durable actor blocks are total: every field is present and unresolved values are
  written as `UNKNOWN`, never JSON/YAML null.

Environment:

```text
ENA_ACTOR_EXECUTOR      who is acting here (e.g. lxc-dsh/session-3d75c2ad)
ENA_INITIATED_BY        who asked (e.g. owner, peer:pc-dsh)
ENA_CHANNEL             how it arrived (common values: chat | cli | cron | a2a | api)
ENA_CORRELATION_ID      Host/transport correlation id (e.g. a peer taskId)
ENA_PEER_CALLER         set by a local peer bridge that dispatches this session
ENA_PEER_TASK_ID        set by a local peer bridge that dispatches this session
```

`ENA_CHANNEL` is an open Host/integration token rather than a closed enum; the common
values above are conventions. `attribution_confidence` is currently the small enum
`SELF_ASSERTED | UNKNOWN`. `SELF_ASSERTED` means that one or more populated values came
from an unverified process-environment / Host-integration assertion; it does not make
remaining `UNKNOWN` fields known and it is not an authorization claim.

Namespace note (field finding, Linux session Host 2026-09-12): a first implementation
used `DSH_PEER_CALLER` / `DSH_PEER_TASK_ID` and both were **silently dropped** before
reaching the dispatched session, because the Host runtime filters environment variables
in its own namespace (`DSH_*`). The dispatched artifact then recorded `channel: a2a`
and an executor but no initiator — provenance lost with no error. Attribution variables
therefore use a prefix the Host does not manage; the `DSH_*` names are still accepted as
a fallback for bridges that use them.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Mapping

UNKNOWN = "UNKNOWN"
SELF_ASSERTED = "SELF_ASSERTED"
CHANNEL_A2A = "a2a"

ENV_EXECUTOR = "ENA_ACTOR_EXECUTOR"
ENV_INITIATED_BY = "ENA_INITIATED_BY"
ENV_CHANNEL = "ENA_CHANNEL"
ENV_CORRELATION_ID = "ENA_CORRELATION_ID"
ENV_PEER_CALLER = "ENA_PEER_CALLER"
ENV_PEER_TASK_ID = "ENA_PEER_TASK_ID"
# Fallback for bridges that use the Host runtime namespace. On at least one real Host
# those variables never reached the dispatched session (silently filtered), so they are
# not the primary contract.
ENV_PEER_CALLER_FALLBACK = "DSH_PEER_CALLER"
ENV_PEER_TASK_ID_FALLBACK = "DSH_PEER_TASK_ID"


@dataclass(frozen=True)
class Actor:
    executor: str
    initiated_by: str
    channel: str
    correlation_id: str | None
    attribution_confidence: str


def _clean(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def resolve_actor(env: Mapping[str, str] | None = None) -> Actor:
    """Resolve the smallest useful attribution block from the process environment."""
    env = os.environ if env is None else env

    executor = _clean(env.get(ENV_EXECUTOR))
    initiated_by = _clean(env.get(ENV_INITIATED_BY))
    channel = _clean(env.get(ENV_CHANNEL))
    correlation_id = _clean(env.get(ENV_CORRELATION_ID))

    # A local peer bridge that dispatches a headless session can say who called it.
    # Without that, the dispatched session would have no way to know.
    caller = _clean(env.get(ENV_PEER_CALLER)) or _clean(env.get(ENV_PEER_CALLER_FALLBACK))
    task_id = _clean(env.get(ENV_PEER_TASK_ID)) or _clean(env.get(ENV_PEER_TASK_ID_FALLBACK))
    if initiated_by is None and caller:
        initiated_by = f"peer:{caller}"
    if channel is None and caller:
        channel = CHANNEL_A2A
    if correlation_id is None and task_id:
        correlation_id = task_id

    supplied = any((executor, initiated_by, channel, correlation_id))
    return Actor(
        executor=executor or UNKNOWN,
        initiated_by=initiated_by or UNKNOWN,
        channel=channel or UNKNOWN,
        correlation_id=correlation_id,
        attribution_confidence=SELF_ASSERTED if supplied else UNKNOWN,
    )


def actor_block(actor: Actor) -> dict[str, object]:
    """Return the total durable actor block; unresolved fields are `UNKNOWN`, never null."""
    return {
        "executor": actor.executor,
        "initiated_by": actor.initiated_by,
        "channel": actor.channel,
        "correlation_id": actor.correlation_id or UNKNOWN,
        "attribution_confidence": actor.attribution_confidence,
    }


def _yaml_scalar(value: object) -> str:
    if value is None:
        return UNKNOWN
    text = str(value)
    if text and all(c.isalnum() or c in "-_./:@+" for c in text):
        return text
    return json.dumps(text, ensure_ascii=False)


def actor_yaml_block(actor: Actor) -> str:
    """Nested `actor:` section for the strict control subset (one mapping level)."""
    block = actor_block(actor)
    return (
        "actor:\n"
        f"  executor: {_yaml_scalar(block['executor'])}\n"
        f"  initiated_by: {_yaml_scalar(block['initiated_by'])}\n"
        f"  channel: {_yaml_scalar(block['channel'])}\n"
        f"  correlation_id: {_yaml_scalar(block['correlation_id'])}\n"
        f"  attribution_confidence: {_yaml_scalar(block['attribution_confidence'])}\n"
    )


def main() -> int:
    """Print the resolved durable attribution block (small Host-integration helper)."""
    actor = resolve_actor()
    print(json.dumps(actor_block(actor), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
