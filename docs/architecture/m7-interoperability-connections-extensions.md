# M7 — Interoperability, Connections & Extension Platform

## Promise

Makolo decides. Providers execute a specialized capability. Extensions compose explicitly authorized capabilities. Canonical domains remain the source of truth.

A Connection gives a channel. Permission/Mandate gives authority. An Action executes a contract. The canonical domain keeps the truth.

## Capability / Provider

`interoperability.registry` describes provider-neutral capabilities, installed providers and exact provider/capability adapters. Installation is availability only; it never grants authorization.

Existing domain adapters remain domain-owned. Payments and Spatiotemporal are not moved into M7. Intelligence keeps its persisted provider configuration and credential lifecycle.

## Connections

`interoperability.connections.ConnectionRef` is a minimal authorization projection. It carries scope, target and enabled state, but no secret or provider configuration.

The first concrete persisted implementation remains `intelligence.ProviderConnection`. `intelligence.interoperability.authorize_provider_connection` maps it to the M7 contract:

- Profile Connection: only its owning Profile may use it;
- Space Connection: current `space.manage` authority is required;
- platform Connection: current `platform.manage` authority is required;
- disabled Connection: rejected before use.

Membership is never authority. Revoking a Mandate removes the actor's authority without deleting the Connection or its history.

## Actions

`interoperability.actions` provides stable Action contracts. An Action declares a code, capability, owner domain, authorization policy, Connection requirement and optional idempotency requirement.

Execution order is intentional:

1. resolve Action and capability;
2. authorize the actor in the Makolo authority context;
3. authorize the Connection when required;
4. enforce idempotency contract when declared;
5. delegate to the owner-domain handler/service.

The Action layer does not mutate canonical models directly and does not become a generic task manager.

## Domain Events and webhooks

M7 reuses the existing `domain_events` outbox and consumer registry. No second event bus or scheduler is introduced.

`interoperability.webhooks` defines signing and delivery contracts for controlled external delivery:

- HMAC-SHA256 signature over `timestamp.body`;
- constant-time signature comparison;
- bounded timestamp window;
- caller-provided replay claim for dedupe/idempotence;
- outbound HTTPS only;
- minimal payload built explicitly per subscription;
- only a signing-key reference is held by the subscription contract;
- secret resolution and transport are injected by the runtime.

M7 therefore does not invent a production secret manager. A runtime without a configured key resolver cannot deliver a signed webhook.

Inbound provider handling must follow: authenticity -> replay/dedupe -> payload validation -> adapter -> owner-domain service. Direct model mutation is out of contract.

## Extension surfaces

`interoperability.extensions` is an allowlist registry. Extensions may compose only explicitly exposed:

- Actions;
- Domain Event types;
- read projections;
- UI slots.

The registry exposes no arbitrary Python execution, ORM, raw SQL, filesystem, credentials, general private-data access, package installer, marketplace or second permission system.

Read projections and UI slots remain presentation/access contracts; they do not own canonical facts. Public or collective projections must apply minimal disclosure.

## Provider health and errors

Provider health remains technical availability, never business truth. Domain adapters should normalize vendor-specific failures before they cross the M7 boundary. Network timeouts and rate limits must remain bounded and observable; infinite retries are out of contract.

## M8 handoff

M7 exposes backend contracts that M8 can assemble into the mature web experience without creating a plugin runtime in the client. M8 may surface Connection state, controlled Actions and extension UI slots contextually, while preserving:

- authority from Permission/Mandate;
- canonical truth in owner domains;
- minimal disclosure;
- no secret material in templates, logs, events or public APIs;
- no mobile-native secure storage/background integration assumptions.

## Exit contract

M7 is converged when the registry, Connection authorization, Action execution, signed webhook contract and controlled extension surfaces pass CI on current `main`, and the final branch is reconciled against current `main` before merge.
