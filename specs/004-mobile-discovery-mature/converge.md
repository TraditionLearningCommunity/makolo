# Converge: Mobile Mature Discover

**Base**: `main@297a4c635dafc49d78a95fd463a30a13ffa5ef54`  
**Branch**: `feat/mobile-discovery-mature`

## Collision audit

- branch is ahead of current `main` and not behind at convergence time;
- PR #446 (Mobile Now) is disjoint from `mobile/lib/features/discovery/**`;
- PR #449 is Web/public only and remains untouched;
- no router, shell, sync engine, ProfileStore, Drift schema, design foundation or migrations changed.

## Implemented

- G03 Compact possibility field using shared ContentFrame/Card/Metadata/Media primitives;
- G04 Wide adaptive grid using `MakoloAdaptiveGrid`;
- Wide N2 selection using the shared AdaptiveSplit/FocusPane geometry while keeping the field present;
- G05 Wide Spatial using `MakoloSpatialFrame` and points derived from the same `discovery.items` collection;
- no production dependency on `discovery.map` as a second G05 dataset;
- query/filter preservation in `DiscoveryQuery`;
- explicit NO_MATCH / END_OF_FIELD / NO_CURRENT_PROPOSAL / OFFLINE_WITH_SNAPSHOT / OFFLINE_NO_SNAPSHOT;
- local snapshot preservation during refresh failure;
- media via `MakoloMediaFrame`;
- save/unsave repository and owner detail contracts preserved.

## COMMON GAP

The shared Maps/router seams do not currently expose everything required for complete spatial restoration:

1. `ConfiguredMakoloMapView` has no shared marker/annotation model.
2. It has no camera-change callback/controller for exact center + zoom persistence.
3. The protected `/discover/map` router seam does not currently carry a `DiscoveryQuery` from Search/root into the map route.

This lane does not duplicate MapLibre, mutate the router or invent local spatial truth.

Minimum integrator follow-up:
- add a shared annotation/selection contract to the Maps foundation;
- expose bounded camera state restoration;
- add a router-owned query/context handoff for Discover spatial mode.

Potentially affected lanes: Discover and future spatial/Jour J surfaces.

## Validation status before PR

- structural source audit: PASS;
- protected-file audit: PASS;
- production `dev/**` / `PresentationFixtureUniverse` imports: none;
- branch vs main: ahead, 0 behind;
- local Flutter/Dart execution: unavailable in the current worker because no Flutter/Dart SDK and no network clone capability are present;
- official `Mobile CI` will execute format, architecture guard, analyze and full non-golden Flutter tests because feature files changed.

## Merge gate

PR remains open and unmerged. Mobile CI is authoritative. Any branch-caused failure must be fixed before handoff.
