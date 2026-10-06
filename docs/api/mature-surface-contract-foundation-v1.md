# Makolo — Mature Surface Contract Foundation v1

> Status: C0 contract foundation for Web and Flutter implementers.
> Reconciled base: `main@609003082219f86000f04d0b7761e53d60077aa8`.
> Reconciliation: the #478 OpenAPI/schema/gate infrastructure is reused directly; C0 feeds that infrastructure and does not duplicate it.

## 0. Purpose

C0 freezes the shared request/response boundary for the primary Mature surfaces before parallel implementation waves.

It is not a server rewrite, not a Flutter rewrite, not a Web redesign, and not a new domain model. It converts the consolidated conceptual UX contracts into implementation-facing request/response expectations, fixtures, and acceptance checks.

```text
conceptual UX contract
  -> request/response contract
  -> fixture
  -> OpenAPI / contract gate
  -> server / Web / Flutter
```

## 1. Non-negotiable rules

1. The server owns shared truth, authority checks, permissions, visibility, freshness and sensitive decisions.
2. The client owns continuity of experience, local cache, recovery, display composition and safe local state.
3. Presentation translates facts; it does not own them.
4. A UX unit is not automatically a response root, a local store object, a view model, or a database model.
5. No surface may create a second Readiness, Access, Capacity, Requirement, Proof, Payment, Permission or Mandate truth.
6. A client may express context, filters, perspective, continuation and interaction intent only where the surface contract allows it.
7. A client may not claim authority, readiness, access, payment, mandate, permission or relevance as truth.

Forbidden client claims, unless an explicit owner action contract says otherwise:

```text
profile_id for /me
authority=true
permission=...
mandate=...
is_relevant=true
is_urgent=true
readiness=ready
requirement_satisfied=true
access_granted=true
payment_confirmed=true
space_authority=true
```

## 2. Common request envelope

Every request, including GET requests, has a contract.

Common fields are conceptual; they may be encoded as path parameters, query parameters, headers, body fields or derived request context.

```json
{
  "viewer": "authenticated Profile resolved from request.user",
  "actor_context": "profile | space",
  "responsibility_context": "optional, server-validated",
  "exploration_context": "optional, server-validated",
  "continuation": "optional opaque cursor/token",
  "client_context": "optional display/local continuity hints only"
}
```

The viewer is always the authenticated Profile. The actor is resolved by the server from the request and the allowed scope.

## 3. Common response envelope

Surface responses SHOULD preserve this shape unless an existing endpoint already has a compatible owner contract.

```json
{
  "surface": "now_me",
  "actor": {"type": "profile", "id": "self", "label": "Moi"},
  "viewer": {"type": "profile", "id": "self"},
  "generated_at": "2026-10-06T11:35:29Z",
  "freshness": {"state": "fresh|stale|partial|unavailable", "observed_at": null},
  "selection": {"state": "ready|empty|partial|unavailable", "reason": null},
  "capabilities": [],
  "handoffs": [],
  "items": [],
  "continuation": null,
  "terminal": {"state": "ok|empty|blocked|unavailable", "message": null}
}
```

The response may include other owner-provided fields, but must not require Web or Flutter to infer domain truth from visual-only fields.

## 4. Surface contracts

### 4.1 Now Me

```text
Purpose: answer “Qu’est-ce qui compte maintenant ?” for the authenticated Profile.
Method/path: GET /api/v1/me/now/
Actor: authenticated Profile, resolved from request.user.
Viewer: authenticated Profile.
```

Request contract:

- no arbitrary `profile_id` selector;
- optional continuation only if server supports it;
- optional safe display/local context only as a hint;
- no client claim of urgency, readiness, authority or access.

Response contract:

- root surface: `now_me`;
- root actor attention state: `active|calm`, established by the server;
- collection: attention situations, possibly empty;
- each item carries an opaque stable continuity identity and explains state, structured why-now basis, consequence target/effect, turn, response, horizon and owner handoff/depth;
- machine codes remain available for reconciliation, while `state_meaning` and `why_now.meaning` carry owner-backed human meaning; clients never display or translate a code as meaning;
- when an owner has not established a distinct consequence, `consequence.state` is `unknown` and `consequence.effect` is null rather than a renamed summary;
- `why_now`, `consequence`, `turn`, authority and knowledge semantics are server projections and are never reconstructed by a client;
- terminal empty is valid and may allow Presentation to say “Tout est en ordre. ✓”; that wording is not authoritative server truth.

Server responsibilities:

- compose only legitimate visible facts;
- preserve Assignment vs Permission/Mandate;
- expose action capabilities only after server authorization.

Client responsibilities:

- render attention without creating a dashboard or todo list;
- preserve recovery/offline states from the common behavior contract;
- never unlock actions from UI-only state.

### 4.2 Discover Me

```text
Purpose: expose the personal field of possibilities to explore.
Method/path: GET /api/v1/discovery/items/
Actor: authenticated Profile.
Viewer: authenticated Profile.
```

Request contract:

- may include query, filters, sort, map bounds, exploration context and continuation where supported;
- may not submit a relevance score, match percentage or global rank as truth;
- may not claim a Bookmark/Watch/Intent as engagement unless the owner action contract records it.

Response contract:

- root surface: `discover_me`;
- collection: possibility projections;
- each item must be traceable to a minimal canonical basis or existing owner identity;
- include known/favorable/limiting/unknown state only when owner-provided or safely derived upstream;
- empty, partial and unavailable are first-class states.

Server responsibilities:

- provide the field selected by owner domains/intelligence;
- preserve provenance and identity stability;
- avoid popularity, trending and infinite-feed semantics.

Client responsibilities:

- support exploration, filtering, comparison and map/list layout without owning ranking;
- avoid converting visibility into desire or engagement.

### 4.3 Ongoing Me / En cours

```text
Purpose: show what the Profile has genuinely engaged and what continues.
Method/path: GET /api/v1/me/ongoing/
Actor: authenticated Profile.
Viewer: authenticated Profile.
```

Request contract:

- no arbitrary profile selector;
- optional filters such as status family, horizon or owner family only where server-supported;
- no claim that a backend relation is a personal continuity.

Response contract:

- root surface: `ongoing_me`;
- collection: continuity projections;
- each continuity must satisfy personal relation, effective pursuit, continuation, remaining relevance and legitimate visibility;
- include what is settled, what remains on the Profile side, what continues elsewhere, what Makolo prepares/watches and next handoff when available.

Server responsibilities:

- compose owner facts without creating `Continuity` as a domain truth;
- keep personal and Space contexts distinct.

Client responsibilities:

- preserve cognitive return and master/detail continuity;
- never treat Assignment in a Space as personal engagement.

### 4.4 Moi

```text
Purpose: show what is already in place around the Profile to make future action easier.
Method/path: GET /api/v1/me/
Actor: authenticated Profile.
Viewer: authenticated Profile.
```

Request contract:

- no arbitrary profile selector;
- may request safe sections where endpoint already supports it;
- may not infer public visibility from private existence.

Response contract:

- root surface: `me`;
- sections may include identity, passport, considerations, collectives, resources, support and links when supported;
- every section must distinguish known, missing, private, unavailable and unsupported states.

Server responsibilities:

- expose only minimal necessary personal facts;
- preserve Profile as a global person, not a global participant/organizer.

Client responsibilities:

- render stable personal territory and recovery;
- never turn private Profile facts into public projections.

### 4.5 Mark Me

```text
Purpose: let the Profile give Makolo something to interpret, save, prepare or route.
Method/path: POST /api/v1/me/mark/
Actor: authenticated Profile.
Viewer: authenticated Profile.
```

Request contract:

- body may include text, file reference, URL, scan/camera payload metadata, intent or target owner when supported;
- client-provided interpretation is only an input, not truth;
- no client claim that a requirement is satisfied, proof accepted, payment confirmed or access granted.

Response contract:

- root surface/action: `mark_me`;
- include accepted/rejected/needs_more/queued/prepared outcome;
- include owner handoff, next safe action, draft preservation and recovery state.

Server responsibilities:

- route to owner domains or intake pipeline;
- avoid orphan content/media; every item needs context and purpose.

Client responsibilities:

- preserve drafts and upload recovery;
- show feedback immediately.

### 4.6 Now Space

```text
Purpose: answer “Qu’est-ce qui mérite notre attention maintenant ?” for a Space actor.
Method/path: GET /api/v1/organizations/workspaces/{space_slug}/now/
Actor: Space resolved from path and viewer authority/visibility.
Viewer: authenticated Profile.
```

Request contract:

- path `space_slug` is resolved by server;
- optional responsibility context only after server validation;
- no client claim of Space authority.

Response contract:

- root surface: `now_space`;
- collection: attention situations for the Space perspective;
- selection may be `unavailable` when no safe selector exists;
- include owner handoffs and operation context, not raw module dashboards.

### 4.7 Discover Space

```text
Purpose: expose possibilities that could help the Space advance.
Method/path: GET /api/v1/organizations/workspaces/{space_slug}/discover/
Actor: Space resolved from path and viewer authority/visibility.
Viewer: authenticated Profile.
```

Request contract:

- may include exploration context, query, filters, sort, map bounds and continuation where supported;
- no client claim of collective relevance or authority.

Response contract:

- root surface: `discover_space`;
- collection: collective possibility projections;
- can return empty/unavailable safely while preserving the contract.

### 4.8 Métier Space

```text
Purpose: show what the Space actually operates, in its contextual business language.
Method/path: GET /api/v1/organizations/workspaces/{space_slug}/work/
Actor: Space.
Viewer: authenticated Profile.
```

Request contract:

- optional business perspective and responsibility filters if server-supported;
- no generic `Ongoing Space` surface is created.

Response contract:

- root surface: `space_work`;
- collections are contextualized by archetype/business grammar;
- Ongoing is a dimension inside Métier, not a separate primary gate.

### 4.9 Nous

```text
Purpose: show who the Space is and how it works together.
Method/path: GET /api/v1/organizations/workspaces/{space_slug}/us/
Actor: Space.
Viewer: authenticated Profile.
```

Request contract:

- path Space resolved by server;
- optional section filters only where supported;
- no client claim that membership grants authority.

Response contract:

- root surface: `space_us`;
- include identity, organization, roles/responsibilities summary, visible teams/groups and authority-safe links when supported;
- expose minimal disclosure for collective/public projections.

### 4.10 Mark Space

```text
Purpose: let an authorized Profile give Makolo something in the context of a Space.
Method/path: POST /api/v1/organizations/workspaces/{space_slug}/mark/
Actor: Space, subject to viewer authority.
Viewer: authenticated Profile.
```

Request contract:

- body may include payload, intake type, responsibility/business context and draft metadata;
- client may state intent, not authority or final interpretation.

Response contract:

- root surface/action: `mark_space`;
- include accepted/rejected/needs_authority/needs_more/queued/prepared outcome;
- include owner handoff, operation context and recovery state.

## 5. Error, partial and unavailable semantics

Use these states instead of forcing empty lists to mean every kind of absence.

```text
empty        server knows there is nothing to show for this surface now
partial      server has enough to render but with incomplete coverage
unavailable  server cannot safely compute or expose this surface now
forbidden    viewer lacks legitimate visibility or authority
auth_required viewer is not authenticated
stale        data can render but freshness must be shown
```

## 6. Cache and freshness

- Clients may cache personal/Space projections according to local-first rules.
- Cached data does not become authority.
- Server responses must carry enough freshness/selection state for the client to avoid pretending that old data is current.
- Sensitive actions remain remote-authoritative.

## 7. Acceptance checks for C0

- [ ] No new database model or migration is introduced by C0.
- [ ] PR #478 OpenAPI infrastructure is reused or reconciled before any schema/gate change.
- [ ] Every primary surface has a documented actor, viewer, request contract and forbidden claims.
- [ ] Personal surfaces never accept arbitrary Profile selectors.
- [ ] Space surfaces validate Space visibility/authority server-side.
- [ ] No standalone `Ongoing Space` primary surface is introduced.
- [ ] Every response has explicit empty/partial/unavailable semantics.
- [ ] Fixtures cover at least one ready and one unavailable/empty state.
- [ ] Web and Flutter can implement against the same fixture semantics without deriving domain truth locally.
