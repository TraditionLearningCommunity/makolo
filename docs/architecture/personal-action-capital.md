# Personal Action Capital — Q1/Q2/Q3

## Q1 base

Q_BASE_SHA: `0b368d0f91edce352265fdaefd2ae2978da0e76b`

Q1 introduced the bounded context `personal_assets` and the product surface **Ma Bibliothèque** around two canonical concepts:

- `PersonalAsset`: durable personal identity controlled by exactly one user;
- `PersonalAssetVersion`: immutable private file version with explicit `supersedes` history.

The controller is the Q1 authorization root. The subject can be the controller, another Profile, or an owned `ExternalBeneficiary`, but subject identity never grants control. Files use the existing private Journey artifact storage and canonical upload validation. No public URL is exposed.

## Q2 — Library UX + Controlled Reuse

Q2 branches from validated Q1 HEAD `5538520b8d9b0053044e9b9d130a3486070b670b` and adds explicit, user-triggered reuse in both directions.

### PersonalAssetVersion → JourneyArtifact

`use_personal_asset_version_in_journey()` first scopes the selected version by `asset.controller == actor`, then delegates Journey authorization, upload validation, private storage and JourneyArtifact creation to canonical Journey services. A new file snapshot is created under the Journey contract; the JourneyArtifact never aliases a mutable PersonalAsset file.

`PersonalAssetUse` records the exact `PersonalAssetVersion`, exact `JourneyArtifact`, actor and timestamp.

**Journey history is immutable with respect to later PersonalAsset updates.** If v1 is used in a Journey and v2/v3 are later created, the JourneyArtifact continues to contain and hash v1.

### JourneyArtifact → PersonalAssetVersion

`save_journey_artifact_to_library()` first calls canonical `artifact_for_download()` so normal/restricted Journey permissions remain authoritative. The exact bytes are copied into a new PersonalAssetVersion. `source_journey_artifact` records explicit provenance. The source JourneyArtifact is never moved or mutated.

When copying into an existing PersonalAsset, Q2 may raise the asset sensitivity to the more restrictive source sensitivity; it never silently reduces sensitivity.

### Boundaries

Q2 does not add Requirement satisfaction, Proof/trust state, persisted Readiness, Action Memory, recommendation scoring, Trusted Reuse, Sharing reconciliation, scheduler or notifications. Reuse is explicit and user initiated. Q3 starts from the validated Q2 HEAD rather than from `main`.

## Q3 — Action Memory

Q3 starts from validated Q2 HEAD `a6ff12ac7ba77e975163e6980bfdf2ad5173833b` and remains stacked on Q2. It does not import Sharing or any commit from `main`.

Action Memory implements the promise **« Vous avez déjà fait une partie de ce travail. »** as a read model over existing canonical facts. Q3 does **not** introduce an `ActionMemory` model, table, migration, file store, Requirement state, Proof state or Readiness state.

### Sources composed

Q3 composes three sources only:

1. **Ma Bibliothèque** — `PersonalAsset` plus the current `PersonalAssetVersion` for assets controlled by the actor and whose explicit subject matches the current Journey subject. Archived assets are not proposed as current candidates. The read model uses metadata (`kind`, version, `issued_at`, `expires_at`, `content_hash`, sensitivity and provenance) and never opens the file payload.
2. **Historical JourneyArtifact** — artifacts from previous Journeys for the same explicit subject, but only after canonical Journey authorization. A collaborator assigned to Journey B does not gain visibility into Journey A. `artifacts_for_actor()` remains authoritative for normal/sensitive/restricted artifact visibility. Superseded artifact versions are not proposed as the current historical candidate.
3. **Trust / Proof** — `Proof` rows for the Profile subject, constrained to historical Journeys the actor is legitimately allowed to know. `is_public` is deliberately not used as an Action Memory authorization bypass. A revoked Proof remains visible only as revoked and is never relabelled active.

Q3 deliberately does not add a generic structured-answer source because no canonical reusable-data contract exists for arbitrary stored personal fields.

### Candidate contract

`personal_assets.action_memory.ActionMemoryCandidate` is a frozen dataclass. A candidate carries only explainable facts:

- source and stable source identity;
- parent/source context when needed for an existing canonical action;
- explicit subject (`Profile` or `ExternalBeneficiary`);
- provenance, including source Journey or exact Q2 reuse edge when known;
- source kind/type, status and version when applicable;
- safe title;
- relevant date;
- freshness and explicit expiry fact;
- sensitivity;
- content hash when the source already owns one;
- `POTENTIALLY_RELEVANT` read qualification;
- `ALLOWED_TO_PROPOSE` access state;
- stable reason codes;
- confirmation-required signal;
- explicitly permitted proposed action;
- canonical materialization path;
- `observed_at`.

There is no numeric relevance field and no hidden ranking. Result order is deterministic source grouping — Library, historical JourneyArtifact, Proof — not a score.

### Reason codes

Q3 uses stable technical reason codes including:

- `subject.match`;
- `library.available`;
- `library.current_version`;
- `library.expired`;
- `library.sensitive`;
- `library.restricted`;
- `journey.previous_artifact`;
- `journey.sensitive`;
- `journey.restricted`;
- `proof.active`;
- `proof.revoked`;
- `freshness.not_expired`;
- `freshness.expired`;
- `freshness.unknown`;
- `confirmation.required`.

These codes explain why an item was surfaced. They never assert that a Requirement is satisfied.

### Permission model

Detection is scoped by the current Journey first: `action_memory_for_journey()` calls canonical Journey access checks before inspecting history.

Library authorization remains rooted in `PersonalAsset.controller`. Exact subject equality is a second, independent filter; subject identity never grants control. This preserves controller ≠ subject and `ExternalBeneficiary` semantics.

Historical Journey authorization remains Journey-scoped. For a Profile looking at their own history, beneficiary access is canonical. For a collaborator looking at another subject's history, an active assignment on each historical Journey is required before the canonical artifact/Proof checks are applied. New-Journey collaboration alone never reveals old-Journey metadata.

Only candidates the actor may legitimately know are returned. `ALLOWED_TO_PROPOSE` means the metadata may be surfaced in this Action Memory context; it does not grant download, sharing, submission, Requirement acceptance or a new Mandate.

### Freshness

Q3 uses no arbitrary ageing threshold.

For `PersonalAssetVersion`:

- `expires_at < observed local date` → `EXPIRED`;
- explicit `expires_at` today or later → `NOT_EXPIRED`;
- no `expires_at` → `UNKNOWN`.

`issued_at` is preserved as a relevant date but does not create a validity policy by itself. Historical JourneyArtifact and Proof have no generic expiry policy in the current domain contracts, so their Action Memory freshness is `UNKNOWN`.

### Sensitivity and confirmation

`SENSITIVE` and `RESTRICTED` Library/JourneyArtifact candidates keep their exact sensitivity and add `confirmation.required`. Detection never opens or transmits the payload.

An expired Library candidate is surfaced as expired but Action Memory proposes review in Ma Bibliothèque rather than direct reuse. A sensitive or restricted usable candidate requires an explicit user POST before Q2 materializes a snapshot.

### Proposed actions and materialization paths

Q3 creates no second mutation path:

- usable `PersonalAssetVersion` → `USE_IN_JOURNEY` → existing Q2 `PersonalAssetVersion → JourneyArtifact snapshot` service;
- expired or currently non-materializable Library candidate → `REVIEW_LIBRARY` only;
- own accessible historical `JourneyArtifact` → `SAVE_TO_LIBRARY` → existing Q2 `JourneyArtifact → PersonalAssetVersion` service, after which reuse remains a separate explicit action;
- own Profile `Proof` → `VIEW_PROOF` through the existing Trust surface;
- authorized collaborator-only knowledge with no safe owner-domain action → `NONE`.

No Action Memory read creates `PersonalAssetUse`, `JourneyArtifact`, `Proof`, Requirement evidence or any other business row.

### Provenance-aware deduplication

Q3 performs only conservative exact-copy deduplication. A Library candidate and historical JourneyArtifact are collapsed only when an explicit Q2 provenance edge identifies the copy **and** the existing `content_hash` values agree.

Equal hashes without explicit provenance are not merged. Business objects, history and provenance are never deleted or rewritten.

### Action Memory vs Trusted Reuse

Q3 stops before acceptance for a Requirement. `OpportunityRequirement` currently has no general structured `accepted_artifact_kind` or `accepted_proof_type` contract, so Q3 does not inspect `Requirement.title`, description text or fuzzy names to invent a match.

The chain remains:

`Action Memory candidate → explicit user action → canonical JourneyArtifact when needed → explicit Requirement evidence → owner-domain review/acceptance`.

`ServiceRequirementEvidence` continues to require a `JourneyArtifact` belonging to the same Journey as its Assessment. Q3 never attaches an old artifact directly, never changes an Assessment status and never marks a Requirement satisfied.

### Action Memory vs Readiness

Readiness remains a projection owned by its existing domain. Q3 does not persist `is_ready`, `ActionMemoryReadinessState`, `ReuseReadinessState` or any equivalent state. Q3 facts may be consumed later by Prepared Start / Readiness work, but no readiness conclusion is made here.

### Action Memory vs Sharing

Sharing is intentionally absent from Q3 ancestry. Action Memory does not use public/share visibility as authority and does not create a share, delivery or cross-user disclosure path. The Sharing implementation present on current `main` must be reconciled with the complete Q train later; Q3 creates no dependency on `services/reuse_services.py` or other Sharing-only code.

### Minimal UX

The existing Q2 **Utiliser depuis Ma Bibliothèque** page gains an Action Memory panel headed **« Vous avez peut-être déjà ce qu’il faut »**. It shows safe source/freshness/sensitivity/status language and only existing explicit actions. Internal model names, UUIDs, reason codes and scores are not exposed.

The complete Library selector remains available below the panel, so Q3 does not replace Q2 Library UX.

### Q4 handoff

Q4 may build Trusted Reuse from the stable Q3 candidate facts:

- candidate source identity;
- subject;
- provenance and source Journey when applicable;
- source kind/type and status;
- source version;
- sensitivity;
- explicit freshness/expiry facts;
- Proof type/status;
- reason codes;
- allowed proposed action and materialization path;
- `observed_at`.

Q4 must add the missing **contextual acceptance contract** needed to move from `POTENTIALLY_RELEVANT` to **Accepted for this Requirement**. It must not infer that contract from Requirement titles, file names, public Proof flags or content hashes.
