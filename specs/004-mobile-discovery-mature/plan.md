# Implementation Plan: Mobile Mature Discover

**Base SHA**: `297a4c635dafc49d78a95fd463a30a13ffa5ef54`  
**Branch**: `feat/mobile-discovery-mature`  
**Owner**: Discover lane  
**PR target**: `main`

## Brownfield evidence

- `DiscoveryRepository` possède acquisition local-first, snapshots, source-state, refresh et save/unsave.
- `DiscoverySelector` parse la vraie shape `discovery.items` et préserve l’ordre serveur.
- `DiscoveryScreen` est actuellement une liste paginée uniforme.
- `DiscoveryMapScreen` utilise un second snapshot `discovery.map`.
- la projection serveur `discovery.items` contient déjà latitude/longitude pour les possibilités Activity cartographiables.
- la fondation partagée fournit ContentFrame, AdaptiveGrid, SpatialFrame, MediaFrame et états multi-axes.
- PR #446 écrit uniquement Now; aucune collision avec `features/discovery/**`.

## Constitution check

PASS:
- pas de domaine/modèle/persistance nouveau;
- pas de ranking local;
- pas d’autorité dérivée;
- snapshots locaux conservés;
- seams protégés inchangés;
- pas d’import Production depuis dev scenarios;
- changement borné et réversible.

## Design

1. Étendre le selector lane-local pour conserver representation kind, route label et coordonnées owner déjà présentes.
2. Introduire une sélection Presentation Discovery avec états multi-axes et fins explicites.
3. Maturer le champ:
   - Compact: liste naturelle et variée;
   - Wide: `MakoloAdaptiveGrid`;
   - media via `MakoloMediaFrame`.
4. Spatial:
   - dériver les points du même `DiscoveryCollectionPresentation`;
   - `DiscoveryMapScreen` consomme `watchItems`, pas `watchMap`;
   - `MakoloSpatialFrame` contient la carte;
   - sélection partagée entre unités et viewport initial.
5. Préserver repository/API/save/détails owner.
6. Ne pas toucher router, shell, sync, ProfileStore, Drift ni design partagé.

## Files

### Lane files
- `mobile/lib/features/discovery/discovery_repository.dart`
- `mobile/lib/features/discovery/discovery_selector.dart`
- `mobile/lib/features/discovery/discovery_screens.dart`

### Dedicated tests
- `mobile/test/discovery_mature_selector_test.dart`
- `mobile/test/discovery_mature_screen_test.dart`
- tests Discovery existants conservés

### Spec Kit
- `specs/004-mobile-discovery-mature/spec.md`
- `plan.md`
- `tasks.md`
- `analyze.md`
- `converge.md`

## G03/G04/G05 gates

- G03: 360x800, field vertical, media contextuel, aucune action d’engagement inventée.
- G04: 1440x900, `MakoloAdaptiveGrid`, mêmes items/ordre.
- G05: >=1040, `MakoloSpatialFrame`, same-field points, sélection partagée.

## Targeted tests

- parser vraie StoredProjection multi-famille;
- ordre serveur;
- coords dérivées du collection field;
- NO_MATCH / NO_CURRENT_PROPOSAL / END_OF_FIELD;
- offline snapshot / offline no snapshot;
- media présent/absent;
- distant/non-mappable;
- G03/G04/G05;
- textScale 1.6;
- save capability contract;
- aucune dépendance Production directe à dev fixtures.

## Merge gate

PR reste ouverte. CI requise verte avant toute future intégration; aucune fusion automatique.
