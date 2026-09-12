# Agent-to-Agent communication

ENA uses a practical two-way path to other Agents when the Host can support it. Reuse a working Host-native or standards-based A2A implementation when one already exists.

A2A is a collaboration and recovery capability, not a universal installation gate. A human recovery path remains valid on Hosts where A2A is unavailable or unnecessary.

## If A2A already exists

1. Find the Agent Card or discovery record used by the implementation.
2. Verify the advertised endpoint, capabilities and authentication requirements against reality.
3. Complete a real two-way exchange with another Agent.
4. Save stable discovery/config references in `ENA.yaml`.
5. Save current reachability / last-verified state in `SYSTEM.yaml` when that live fact matters to the Host.

Do not create a second ENA identity system when the A2A implementation already provides identity/discovery.

A configured Agent Card reference and a currently working A2A path are different facts. `ENA.yaml` owns the stable configured reference. `SYSTEM.yaml` owns freshness-bounded current reachability/verification. Do not mirror an Agent Card URI into `SYSTEM.yaml` and treat its presence as proof that the peer is live.

## If A2A does not exist

When the Host provides enough capability and a real collaboration need exists:

1. choose the simplest reliable implementation appropriate to the Host;
2. expose/register the Agent using that implementation's normal discovery mechanism;
3. configure authentication and authorization without writing plaintext secrets into ENA records;
4. establish at least one reachable peer;
5. prove a real two-way exchange works;
6. save stable references in `ENA.yaml` and current verification state in `SYSTEM.yaml` when useful.

If the Host does not support a practical A2A path, record the limitation and continue using human/Host recovery rather than blocking the rest of ENA.

## Preserve attribution across dispatched work

A2A identity/discovery and durable action attribution are different concerns. An Agent Card can identify a reachable peer while a later ENA artifact can still lose the fact that the peer initiated the work.

When an A2A bridge can dispatch a child/headless session that may create or change durable ENA state, the bridge should propagate the peer caller and transport task/correlation id into that child session using:

```text
ENA_PEER_CALLER
ENA_PEER_TASK_ID
```

The Host/runtime should also provide `ENA_ACTOR_EXECUTOR` when it can identify the session/process that actually performs the work. `tools/ena_actor.py` derives `initiated_by: peer:<caller>`, `channel: a2a`, and the correlation id from the peer variables without turning any of them into an authorization claim.

Verify the propagation **from inside the dispatched session**, not only in the bridge parent. Run:

```text
python tools/ena_actor.py
```

and confirm the expected `initiated_by`, `channel` and `correlation_id` before claiming that cross-Agent action attribution is available on that Host.

Do not rely on a Host runtime's private namespace for this contract. A real Linux session Host silently filtered `DSH_PEER_CALLER` / `DSH_PEER_TASK_ID` before the child session saw them; `ENA_PEER_*` passed through. The reference helper accepts `DSH_PEER_*` only as a compatibility fallback, not as evidence that the bridge is correctly wired.

If a bridge cannot currently propagate caller/task identity, the A2A path may still be usable for communication. Durable ENA artifacts must then keep the missing attribution as `UNKNOWN`; do not infer a local initiator or treat transport identity as authority.

## Use a rescue peer when A2A is part of recovery

For a risky self-change, an A2A peer can receive the recovery package before live state is modified.

A usable rescue peer should be able to:

- receive `rescue.yaml` and the location of required recovery material;
- acknowledge the exact change package when interactive acknowledgement is part of the recovery plan;
- reach the target Host or recovery mechanism when authorized;
- determine whether communication has returned;
- follow the prepared rollback without reconstructing the target from conversation history.

If the peer can receive messages but cannot actually execute or relay recovery, record that limitation instead of treating delivery alone as rescue capability.

## Protect the rescue path

Changes to networking, authentication, routing, startup or the A2A endpoint can remove the same path needed for rescue.

When A2A is being used as recovery:

- send the recovery package before modifying live state;
- keep any automatic rollback outside the component being changed;
- avoid changing the only recovery channel and its only backup in the same operation;
- require a new real two-way exchange before retaining the change.

See `SAFE-CHANGE.md` for resident versus session/coding Host profiles and human/Agent recovery alternatives.

## Configuration example

Stable configured discovery references belong in `ENA.yaml`. ENA control files use the strict mapping/scalar subset documented in `FIRST-USE.md`; block-sequence YAML (`- item`) is intentionally not accepted by the reference reader. Name peers as mapping keys instead:

```yaml
communication:
  a2a:
    agent_card: https://agent.example.com/.well-known/agent-card.json
    rescue_peers:
      recovery-peer:
        agent_card: https://peer.example.com/.well-known/agent-card.json
        access: configured
```

Current live verification belongs in the freshness-bounded system map, for example:

```yaml
communication:
  a2a_reachability: verified-two-way
```

Use the discovery form supported by the actual A2A implementation. Do not store credentials/private keys in `ENA.yaml` merely to make the reference self-contained.
