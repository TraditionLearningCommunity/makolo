# Convergence: Mobile Mature Now

## Result

**Status**: converged for lane scope, pending PR CI and final batch reconciliation.

## Checks

- Base remains `main@297a4c635dafc49d78a95fd463a30a13ffa5ef54`; branch is not behind main at convergence time.
- Diff touches only Now lane files, dedicated Now tests and this feature's Spec Kit artifacts.
- Production source remains `PersonalRepository.watchNow()`.
- `StoredProjection.payload.items` is adapted without local ranking.
- Unknown/malformed projection shape cannot become false calm.
- Known empty renders `Tout est en ordre. ✓`.
- G01 contract is protected structurally at Compact 360x800.
- G02 contract is protected structurally at Wide 1440x900 and shared 960 split threshold.
- Compact N2 closes back to the retained field state.
- Shared state axes preserve content for offline, pending and recoverable refresh failure.
- No production import from `mobile/lib/dev/**`.
- No changes to design, presentation contracts, dev scenarios/gallery, router, shell, sync, ProfileStore or Drift.
- No model, migration, ranking, Readiness copy, fake success or universal Presentation abstraction added.

## COMMON GAP retained

Production `watchNow()` does not currently expose sync-source reachability or refresh-error state. The lane does not violate protected seams to solve that locally. Presentation behavior is implemented/tested and ready for integrator wiring when the common source-state signal is exposed.

## Golden interpretation

The shared Golden specification defines a Golden as a composition/behavior contract, not only a bitmap. This lane protects G01/G02 through deterministic widget tests and shared geometry keys. It does not fabricate bitmap baselines without a Flutter renderer; CI remains the authoritative execution gate.

## Remaining gate

- Open PR.
- Observe required CI.
- Leave PR open for parallel-batch reconciliation.
