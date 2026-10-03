# Tasks: Mobile Mature — Moi / Me

**Input**: `specs/003-mobile-me-mature/spec.md`, `plan.md`

## Phase 1: Specification & Brownfield
- [X] T001 Lire le contrat commun et les règles Makolo.
- [X] T002 Vérifier main, PR/branches concurrentes, runtime Me/watchMe/personal.me/tests/profondeurs.
- [X] T003 Fixer scope, fichiers interdits, G08/G09, tests et merge gate.

## Phase 2: Selector / Adapter
- [ ] T004 [US1] Créer `mobile/lib/features/me/me_selector.dart` pour adapter la vraie StoredProjection vers MePresentation et détails lane-local.
- [ ] T005 [US1] Isoler empty/error par territoire sans globaliser l'échec.
- [ ] T006 [US2] Mapper freshness/reachability injectables sans inventer le source-state.

## Phase 3: Mature UI
- [ ] T007 [US1] Remplacer le wrapper ProjectionScreen dans `mobile/lib/features/me/me_screen.dart`.
- [ ] T008 [US1] Composer Identity + territoires section-first avec primitives partagées.
- [ ] T009 [US3] Ajouter N2 local avec Back et Focus/Split Wide sans modifier le router.
- [ ] T010 [US3] Respecter G08/G09 et le seuil commun 840.

## Phase 4: Tests
- [ ] T011 [P] Ajouter tests selector full/sparse/empty/error/freshness dans `mobile/test/me_mature_test.dart`.
- [ ] T012 [P] Ajouter tests widget Compact/Wide/N2/offline/textScale dans `mobile/test/me_mature_test.dart`.
- [ ] T013 Vérifier absence de régression de `PersonalRepository.watchMe()` et absence de fake runtime.

## Phase 5: Analyze / Converge
- [ ] T014 Relire code contre FR/SC et invariants; corriger toute divergence.
- [ ] T015 Vérifier diff limité, main courant, PR et CI; laisser PR ouverte.
