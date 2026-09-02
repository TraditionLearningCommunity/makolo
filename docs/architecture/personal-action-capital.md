# Personal Action Capital — Q1/Q2

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
