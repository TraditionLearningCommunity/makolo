# Personal Action Capital — Q1/Q2/Q3/Q4

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

## Q4 — Trusted Reuse + Security / Hardening

Q4 starts from validated Q3 HEAD `3b740fe145b4001e29a89865ce52da1bd26bfbc4`. Q4 remains stacked on Q3 and does not import `main` or Sharing commits.

Trusted Reuse implements the contextual question **« parmi ce que Makolo connaît déjà, qu’est-ce qui est explicitement acceptable pour ce Requirement précis ? »**. There is no universal validity of a document, Proof, historical result or validation. When a structured policy cannot prove acceptance, the correct result is `UNKNOWN`.

### Ownership and contracts

The acceptance policy is owned by the horizontal `requirements` domain because the policy describes what a canonical `OpportunityRequirement` accepts. `personal_assets` continues to own personal documents and Action Memory remains a read projection. Services owns application to a Services Journey because Services owns `ServiceRequirementAssessment` and `ServiceRequirementEvidence`.

Q4 adds two additive Requirements models:

- `RequirementReusePolicy`: an explicit rule attached to one exact Requirement revision. A rule declares one source (`library`, `journey_artifact` or `proof`), an exact `JourneyArtifactKind` or exact `ProofType`, intrinsic-expiry requirements, an optional explicit `max_age_days`, sensitivity/restricted confirmation allowances and whether human review remains required. Policies on published Requirement revisions are immutable; policy changes require Requirement revisioning rather than silent reinterpretation of history.
- `RequirementReuseApplication`: append-only, privacy-safe audit of an application. It references the exact Assessment, policy, exact source object/version, actor, decision facts, confirmation, materialization path, resulting JourneyArtifact/Evidence when applicable and timestamps. It does not duplicate filename, payload, storage path, private URL, extracted content or content hash.

Migrations are additive: `requirements/0001_trusted_reuse_policy.py` and `requirements/0002_trusted_reuse_application.py`.

Q4 deliberately does **not** add `TrustedRequirement`, `ReuseRequirement`, a second Evidence model, an Action Memory persistence model, a Readiness state, a Proof clone or a generic content-type/JSON policy engine.

### Decision contract and explainability

`requirements.trusted_reuse.TrustedReuseDecision` is immutable and carries the Requirement/Assessment context, candidate source identity, policy identity/key, decision, stable reason codes, observed freshness, sensitivity, confirmation requirement, materialization path and `observed_at`.

Decision states distinguish at least `NOT_APPLICABLE`, `UNKNOWN`, `NOT_ACCEPTABLE`, `ACCEPTABLE` and `ACCEPTABLE_WITH_CONFIRMATION`. There is no score, probability, embedding, LLM decision or fuzzy title matching.

Stable reasons include the explicit facts used by the evaluator: no policy, source disallowed, subject mismatch, exact kind mismatch/match, expiration, unknown freshness, explicit freshness window, Proof revocation/type match, sensitivity/restricted confirmation, current Requirement revision, permission denial, human review and confirmation.

### Freshness

Q4 keeps intrinsic and contextual freshness separate. Q3 still supplies `EXPIRED`, `NOT_EXPIRED` or `UNKNOWN` from explicit source facts. A Requirement may add `max_age_days`; that rule is evaluated only against an explicit source date such as `issued_at`. Creation time is not silently reinterpreted as an issuance date. If the policy needs freshness and the source date is unknown, Trusted Reuse returns `UNKNOWN` rather than inventing validity.

### Documents, Proof and subject

For documents, exact `JourneyArtifactKind` matching is mandatory. A Library policy never authorizes a historical JourneyArtifact unless a separate policy allows that source, and vice versa. Equal content hashes never replace source identity, control, provenance or policy.

For Proof, exact `ProofType` and current `ProofStatus` are checked. A revoked Proof is not acceptable. Proof remains a Trust fact and is never converted into a fake `JourneyArtifact`. When a Proof is applied, Q4 records the exact Proof/policy/actor/status in `RequirementReuseApplication`; it does not create `ServiceRequirementEvidence` because the current Services Evidence contract is document/JourneyArtifact based.

Subject equality remains exact. Profile and `ExternalBeneficiary` are distinct subject types. ExternalBeneficiary reuse requires the authorized controller plus exact external subject match; Q4 never invents an authenticated Profile for an external beneficiary.

### Authorization and confirmation

Trusted Reuse composes independent authorization layers rather than deriving authority from visibility:

1. Q3/source authorization decides whether the candidate may be known.
2. Journey/Services authorization decides whether the actor may act on the target Journey.
3. Services authorization governs Evidence submission.
4. Requirement owner workflow governs review/acceptance.
5. Trust authorization/status governs Proof use.

Assignment remains responsibility, not authority. New-Journey collaboration never grants historical-memory access by itself.

Sensitive and restricted candidates are never transmitted on preview/GET. When policy permits them, the decision is `ACCEPTABLE_WITH_CONFIRMATION`; the POST must express explicit confirmation, but the server then reloads the exact candidate and revalidates authorization and policy. A browser `confirmed=true` value never substitutes for permission.

### Evaluation, TOCTOU and application

`evaluate_trusted_reuse()` is read-only. It consumes a Q3 `ActionMemoryCandidate`, the current Assessment/Requirement context and actor, and returns a decision without changing Asset, Artifact, Proof, Assessment, Evidence or Readiness.

`apply_trusted_reuse()` is transactional and does not trust the preview. It reloads and locks the current Assessment, verifies the target Journey is actionable, verifies the current pinned Requirement revision, rebuilds current Action Memory for the exact source identity, reevaluates policy/freshness/revocation/sensitivity, requires confirmation where needed, and only then delegates mutation to owner services.

This closes preview/apply races including source archive, new Library version, expiration boundary, Proof revocation, completed Assessment, closed Journey and permission withdrawal. The exact source version chosen at apply is never silently replaced with a newer version.

### Materialization and Evidence

The document pipeline remains canonical:

`ActionMemoryCandidate → TrustedReuseDecision → explicit apply → Q2 materialization → JourneyArtifact in target Journey → submit_requirement_evidence()`.

For Library, Q2 creates the exact `PersonalAssetVersion → JourneyArtifact` snapshot and `PersonalAssetUse` provenance. For an authorized historical JourneyArtifact, Q4 does not attach it directly to the new Assessment; the supported path is historical Artifact → Q2 save to Library → exact PersonalAssetVersion → Q2 target-Journey snapshot → canonical Evidence.

`ServiceRequirementEvidence` therefore always belongs to the target Assessment Journey. A Trusted Reuse decision does not call `assess_requirement(... SATISFIED ...)`. Human review and completion rules remain owned by Services/Requirements.

### Audit, idempotence and concurrency

The Assessment row is the transactional serialization point for apply. `RequirementReuseApplication` has exact-source uniqueness per Assessment; Q2 `PersonalAssetUse` and canonical Evidence idempotence are reused rather than replaced by a cache. PostgreSQL concurrency tests execute two simultaneous applies and require one application, one materialization and one Evidence.

Audit is intentionally privacy-safe: canonical IDs, policy, stable reason codes, source status/version where applicable, actor and timestamps are sufficient. No new log/error path includes payloads, private URLs, storage paths, hashes or extracted document data.

### Trust PostgreSQL hardening

Q4 fixes the pre-existing PostgreSQL `FOR UPDATE cannot be applied to the nullable side of an outer join` failures without removing transactional locks. The affected Trust queries retain `select_for_update()` but scope the lock to the owner row with `of=("self",)`, so nullable `select_related` joins are not included in the lock target.

### UX

The participant Services Requirement surface exposes **« Vous avez peut-être déjà ce qu’il faut »**. It presents safe source labels and human explanations such as expired, unknown freshness, revoked attestation or human review required. Acceptable documents can be explicitly applied; sensitive/restricted use shows a confirmation explaining that Makolo will copy the item into this Journey and submit it as Evidence to examine. Technical reason codes, policy IDs, internal model names and scores are not shown.

A recognized Proof is shown as an attestation, not a document; the current participant UI does not pretend to create file Evidence from it. If no policy proves acceptance, the UI honestly states that Makolo cannot conclude automatically and the normal workflow remains available.

### Readiness and Sharing boundaries

Q4 adds no persistent Readiness state and performs no background materialization. Future Prepared Start work may call the pure evaluator to ask whether an acceptable candidate exists.

Q4 has no dependency on Sharing. `services/reuse_services.py` on current `main` remains a separate Journey/plan reuse capability. Share envelopes, deliveries or inbound capture grant no PersonalAsset, Proof, Journey, Requirement or acceptance permission.

## Q final reconciliation checklist

After Q4 is validated, freeze the exact Q4 HEAD. The next mission is reconciliation with the **current** `main`, not Q5 and not a rebase of Q4. Create a separate reconciliation branch from current `main`, then compose the whole validated Q train explicitly.

Compare and reconcile at minimum:

- `config/settings.py`: installed apps and any main-only Sharing/M5/M6 wiring;
- `config/urls.py`: preserve both Q routes and all current-main routes;
- navigation and shared templates;
- `core/participant_journey_detail.html` and participant Journey context;
- `templates/services/participant_workspace.html` and Trusted Reuse/Sharing actions;
- `requirements/`: Q4 policy/application migrations and any main-era horizontal Requirement changes;
- `trust/`: Q4 PostgreSQL lock fix versus current-main Trust evolution;
- Readiness contracts/resolver/contributors, without creating a persisted Q state;
- Sharing P1→P5, including privacy and authorization boundaries;
- `services/reuse_services.py`: keep Sharing Journey-plan reuse distinct from Q4 Trusted Reuse;
- Services Assessment/Evidence/review/completion behavior;
- Journey artifact/version/provenance services;
- Domain Events: reuse owner-domain events where sufficient and avoid privacy-unsafe duplicate events;
- frontend source templates/navigation and the repository’s compiled frontend assets;
- CI/workflows, especially Q validation, generic Django, PostgreSQL, beta seed and frontend synchronization;
- migration graph for `requirements`, `personal_assets`, `services`, `trust`, `sharing` and any new current-main apps.

Do not resolve conflicts with a global ours/theirs choice. Compose competing changes file by file. Rebuild committed frontend artifacts after the final source composition if the repository requires them.

Before the final integration PR, run the complete migration check, SQLite/PostgreSQL suites, beta seeds, frontend build/artifact verification and full Django suite. Then smoke-test visitor, authenticated participant, Library controller, controller ≠ subject, ExternalBeneficiary, Journey collaborator, Services operator, staff, Activity/Occurrence, Journey, Personal Assets, Action Memory, Trusted Reuse, Requirements, Proof, Readiness, Sharing, Access, Commerce and Payment where implicated, with no server 500.

Only after that reconciliation gate should the Q train be integrated into `main` once.
